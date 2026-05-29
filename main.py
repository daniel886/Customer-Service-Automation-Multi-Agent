"""Application entry point.

Run locally:
    python main.py
or:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from api import admin as admin_api
from api import routes as public_routes
from api import websocket as websocket_api
from core.config import PROJECT_ROOT, settings
from core.logger import logger
from integrations import wechat_work
from integrations.email_handler import poll_inbox_loop
from models.database import init_db
from scheduler.daily_report import shutdown_scheduler, start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} on {settings.app_host}:{settings.app_port}")
    await init_db()
    scheduler_started = False
    if not settings.test_mode and settings.scheduler_enabled:
        try:
            start_scheduler()
            scheduler_started = True
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(f"Scheduler failed to start, continuing without it: {exc}")
    else:
        logger.info("Scheduler disabled (test_mode or scheduler_enabled=False)")
    email_task: Optional[asyncio.Task] = None
    if not settings.test_mode and settings.email_enabled:
        email_task = asyncio.create_task(poll_inbox_loop())
    try:
        yield
    finally:
        if scheduler_started:
            shutdown_scheduler()
        if email_task:
            email_task.cancel()
        logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "多 Agent 客服自动化系统 — AutoGen + LangGraph + LangChain。"
        "支持企业微信、邮件、网页客服三种入口，多 Agent 协作 + RAG 知识库 + 人工接管。"
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- Routers -----
app.include_router(public_routes.router, tags=["public"])
app.include_router(websocket_api.router, tags=["websocket"])
app.include_router(admin_api.router, prefix="/admin", tags=["admin"])
app.include_router(wechat_work.router, prefix="/integrations", tags=["wechat"])


# ----- Static -----
static_dir = PROJECT_ROOT / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    return RedirectResponse(url="/static/chat.html")


@app.get("/admin")
async def admin_page():
    return FileResponse(str(static_dir / "admin.html"))


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
        log_level=settings.log_level.lower(),
    )
