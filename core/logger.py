"""Loguru-based application logger."""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger as _logger

from core.config import PROJECT_ROOT, settings


def setup_logger() -> None:
    """Configure loguru sinks (stdout + file rotation)."""
    _logger.remove()

    _logger.add(
        sys.stdout,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> "
            "- <level>{message}</level>"
        ),
        backtrace=True,
        diagnose=settings.app_env != "production",
        enqueue=True,
    )

    log_path: Path = PROJECT_ROOT / "logs" / "app.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _logger.add(
        str(log_path),
        rotation="20 MB",
        retention="14 days",
        level=settings.log_level,
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )


setup_logger()

logger = _logger
