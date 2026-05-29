"""Core configuration module powered by Pydantic v2 settings."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# All runtime artefacts live under the project root by default. This
# avoids any reliance on the current working directory or external
# filesystem permissions: the chat-service, scheduler and Chroma all
# share these guaranteed-writable folders.
DEFAULT_DATA_DIR: Path = PROJECT_ROOT / "data"
DEFAULT_LOGS_DIR: Path = PROJECT_ROOT / "logs"
DEFAULT_CHROMA_DIR: Path = DEFAULT_DATA_DIR / "chroma"
DEFAULT_KB_DIR: Path = PROJECT_ROOT / "knowledge_base"


class Settings(BaseSettings):
    """Application settings loaded from environment/.env file."""

    # Application
    app_name: str = Field(default="Customer-Service-Automation-Multi-Agent")
    app_env: str = Field(default="development")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    app_secret_key: str = Field(default="change-me")
    log_level: str = Field(default="INFO")
    test_mode: bool = Field(default=False)  # disables scheduler/email pollers

    # LLM
    openai_api_key: str = Field(default="")
    openai_base_url: str = Field(default="https://api.openai.com/v1")
    openai_model: str = Field(default="gpt-4o-mini")
    openai_embedding_model: str = Field(default="text-embedding-3-small")
    llm_temperature: float = Field(default=0.3)
    llm_max_tokens: int = Field(default=2048)

    # Database — always relative to project root unless an absolute path is given.
    database_url: str = Field(
        default=f"sqlite+aiosqlite:///{DEFAULT_DATA_DIR / 'customer_service.db'}"
    )
    chroma_persist_dir: str = Field(default=str(DEFAULT_CHROMA_DIR))
    knowledge_base_dir: str = Field(default=str(DEFAULT_KB_DIR))

    # WeChat Work
    wechat_work_corp_id: str = Field(default="")
    wechat_work_agent_id: str = Field(default="")
    wechat_work_secret: str = Field(default="")
    wechat_work_token: str = Field(default="")
    wechat_work_aes_key: str = Field(default="")
    wechat_work_callback_path: str = Field(default="/integrations/wechat/callback")

    # Email
    email_enabled: bool = Field(default=False)
    email_provider: str = Field(default="smtp")
    email_username: str = Field(default="")
    email_password: str = Field(default="")
    smtp_host: str = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=465)
    smtp_tls: bool = Field(default=True)
    imap_host: str = Field(default="imap.gmail.com")
    imap_port: int = Field(default=993)
    email_poll_interval_seconds: int = Field(default=60)

    # Scheduler
    daily_report_cron: str = Field(default="0 9 * * *")
    daily_report_timezone: str = Field(default="Asia/Shanghai")
    daily_report_recipients: str = Field(default="")
    scheduler_enabled: bool = Field(default=True)

    # Multi-tenancy
    default_tenant_id: str = Field(default="default")
    multi_tenant_enabled: bool = Field(default=True)

    # Human takeover
    human_takeover_timeout_minutes: int = Field(default=30)
    human_takeover_notify_webhook: str = Field(default="")

    # Admin
    admin_username: str = Field(default="admin")
    admin_password: str = Field(default="admin123")
    jwt_secret: str = Field(default="change-me")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=1440)

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("daily_report_recipients")
    @classmethod
    def _strip(cls, v: str) -> str:
        return (v or "").strip()

    @property
    def daily_report_recipients_list(self) -> List[str]:
        if not self.daily_report_recipients:
            return []
        return [x.strip() for x in self.daily_report_recipients.split(",") if x.strip()]

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    def _resolve_local(self, value: str, fallback: Path) -> Path:
        """Resolve a path string into an absolute project-local path.

        Relative paths are anchored to ``PROJECT_ROOT`` to avoid CWD-dependent
        permission errors. If creation fails, fall back to a guaranteed
        writable directory under the project root.
        """
        p = Path(value).expanduser()
        if not p.is_absolute():
            p = (PROJECT_ROOT / p).resolve()
        try:
            p.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(p, 0o755)
            except PermissionError:
                pass
            return p
        except (PermissionError, OSError):
            fallback.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(fallback, 0o755)
            except PermissionError:
                pass
            return fallback

    def ensure_dirs(self) -> None:
        """Create / repair every runtime directory the chat service needs.

        This guarantees:
        * ``data/`` and ``logs/`` exist with mode 0755 under the project root.
        * Chroma vector store path is writable; falls back to project-local.
        * Knowledge-base path is readable; falls back to project-local.
        * SQLite URLs are normalised to absolute paths so that no chat
          message / session write is ever blocked by a missing directory.
        """
        for d in (DEFAULT_DATA_DIR, DEFAULT_LOGS_DIR):
            d.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(d, 0o755)
            except PermissionError:
                pass

        chroma = self._resolve_local(self.chroma_persist_dir, DEFAULT_CHROMA_DIR)
        kb = self._resolve_local(self.knowledge_base_dir, DEFAULT_KB_DIR)
        self.chroma_persist_dir = str(chroma)
        self.knowledge_base_dir = str(kb)

        # Normalise sqlite URL to an absolute project-local path.
        if self.database_url.startswith("sqlite") and ":///" in self.database_url:
            scheme, raw_path = self.database_url.split(":///", 1)
            db_path = Path(raw_path).expanduser()
            if not db_path.is_absolute():
                db_path = (PROJECT_ROOT / raw_path).resolve()
            try:
                db_path.parent.mkdir(parents=True, exist_ok=True)
            except (PermissionError, OSError):
                db_path = DEFAULT_DATA_DIR / "customer_service.db"
                db_path.parent.mkdir(parents=True, exist_ok=True)
            self.database_url = f"{scheme}:///{db_path}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s


settings = get_settings()
