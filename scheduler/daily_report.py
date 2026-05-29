"""APScheduler-based daily report job."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import func, select

from core.config import settings
from core.logger import logger
from integrations.email_handler import send_email
from models.database import DailyReport, Message, Session as DBSession, Ticket, get_session


_scheduler: Optional[AsyncIOScheduler] = None


async def generate_daily_report(tenant_id: Optional[str] = None) -> dict:
    """Aggregate yesterday's stats, persist a DailyReport, and return it."""
    tenant_id = tenant_id or settings.default_tenant_id
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)
    start = datetime(yesterday.year, yesterday.month, yesterday.day)
    end = start + timedelta(days=1)

    async with get_session() as db:
        sess_total = await db.scalar(
            select(func.count(DBSession.id)).where(
                DBSession.tenant_id == tenant_id,
                DBSession.created_at >= start,
                DBSession.created_at < end,
            )
        )
        msg_total = await db.scalar(
            select(func.count(Message.id)).where(
                Message.created_at >= start, Message.created_at < end
            )
        )
        resolved = await db.scalar(
            select(func.count(DBSession.id)).where(
                DBSession.tenant_id == tenant_id,
                DBSession.status == "closed",
                DBSession.updated_at >= start,
                DBSession.updated_at < end,
            )
        )
        escalated = await db.scalar(
            select(func.count(DBSession.id)).where(
                DBSession.tenant_id == tenant_id,
                DBSession.status == "takeover",
                DBSession.updated_at >= start,
                DBSession.updated_at < end,
            )
        )
        ticket_total = await db.scalar(
            select(func.count(Ticket.id)).where(
                Ticket.tenant_id == tenant_id,
                Ticket.created_at >= start,
                Ticket.created_at < end,
            )
        )

        narrative = (
            f"【{settings.app_name} 每日客服日报 {yesterday.isoformat()}】\n"
            f"租户: {tenant_id}\n"
            f"会话总数: {sess_total or 0}\n"
            f"消息总数: {msg_total or 0}\n"
            f"已解决会话: {resolved or 0}\n"
            f"升级人工会话: {escalated or 0}\n"
            f"新增工单: {ticket_total or 0}\n"
        )

        rep = DailyReport(
            tenant_id=tenant_id,
            date=yesterday.isoformat(),
            total_sessions=int(sess_total or 0),
            total_messages=int(msg_total or 0),
            resolved=int(resolved or 0),
            escalated=int(escalated or 0),
            avg_response_time=0.0,
            content=narrative,
        )
        db.add(rep)

    logger.info(f"Generated daily report for {tenant_id} {yesterday}")

    if settings.daily_report_recipients_list:
        for to in settings.daily_report_recipients_list:
            await send_email(
                to=to,
                subject=f"[{settings.app_name}] 客服日报 {yesterday.isoformat()}",
                body=narrative,
            )

    return {
        "tenant_id": tenant_id,
        "date": yesterday.isoformat(),
        "narrative": narrative,
    }


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    sched = AsyncIOScheduler(timezone=settings.daily_report_timezone)
    try:
        trigger = CronTrigger.from_crontab(
            settings.daily_report_cron, timezone=settings.daily_report_timezone
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Invalid DAILY_REPORT_CRON, fallback 09:00: {exc}")
        trigger = CronTrigger(hour=9, minute=0)
    sched.add_job(generate_daily_report, trigger=trigger, name="daily-report")
    sched.start()
    _scheduler = sched
    logger.info("Scheduler started")


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")
