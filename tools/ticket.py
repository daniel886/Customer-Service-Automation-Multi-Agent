"""Ticket / work-order helpers."""
from __future__ import annotations

import uuid
from typing import Literal, Optional

from sqlalchemy import select

from core.config import settings
from core.logger import logger
from models.database import Ticket, get_session


async def create_ticket(
    session_id: str,
    title: str,
    description: str,
    category: Literal["complaint", "tech", "aftersales", "consult"] = "consult",
    priority: Literal["low", "normal", "high", "urgent"] = "normal",
    tenant_id: Optional[str] = None,
    assignee: Optional[str] = None,
) -> str:
    """Create a ticket and return its id."""
    ticket_id = f"T-{uuid.uuid4().hex[:10].upper()}"
    async with get_session() as db:
        db.add(
            Ticket(
                id=ticket_id,
                session_id=session_id,
                tenant_id=tenant_id or settings.default_tenant_id,
                title=title[:240],
                description=description,
                category=category,
                priority=priority,
                assignee=assignee,
            )
        )
    logger.info(f"Ticket created: {ticket_id} ({category}/{priority})")
    return ticket_id


async def list_tickets(
    tenant_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[Ticket]:
    async with get_session() as db:
        stmt = select(Ticket).order_by(Ticket.created_at.desc()).limit(limit)
        if tenant_id:
            stmt = stmt.where(Ticket.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(Ticket.status == status)
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows)


async def update_ticket_status(
    ticket_id: str, status: Literal["open", "in_progress", "resolved", "closed"]
) -> bool:
    async with get_session() as db:
        row = (
            await db.execute(select(Ticket).where(Ticket.id == ticket_id))
        ).scalar_one_or_none()
        if row is None:
            return False
        row.status = status
        return True
