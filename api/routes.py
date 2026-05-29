"""Public chat / ticket / KB API routes."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from sqlalchemy import func, select

from core.chat_service import chat_service
from core.config import settings
from core.logger import logger
from models.database import Message, Session as DBSession, Ticket, get_session
from models.schemas import (
    ChatRequest,
    ChatResponse,
    MessageOut,
    SessionOut,
    StatsOut,
    TakeoverReplyRequest,
    TakeoverRequest,
    TicketCreate,
    TicketOut,
)
from tools.knowledge_base import kb
from tools.ticket import create_ticket, list_tickets

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "env": settings.app_env}


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if not req.message.strip():
        raise HTTPException(400, "message must not be empty")
    result = await chat_service.handle_user_turn(
        message=req.message,
        session_id=req.session_id,
        tenant_id=req.tenant_id,
        channel=req.channel,
        customer_id=req.customer_id,
        customer_name=req.customer_name,
        metadata=req.metadata,
    )
    return ChatResponse(**result)


@router.get("/sessions", response_model=List[SessionOut])
async def list_sessions(
    tenant_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
):
    async with get_session() as db:
        stmt = select(DBSession).order_by(DBSession.updated_at.desc()).limit(limit)
        if tenant_id:
            stmt = stmt.where(DBSession.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(DBSession.status == status)
        rows = (await db.execute(stmt)).scalars().all()
    return [SessionOut.model_validate(r) for r in rows]


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def get_session_detail(session_id: str):
    async with get_session() as db:
        row = (
            await db.execute(select(DBSession).where(DBSession.id == session_id))
        ).scalar_one_or_none()
        if not row:
            raise HTTPException(404, "session not found")
    return SessionOut.model_validate(row)


@router.get("/sessions/{session_id}/messages", response_model=List[MessageOut])
async def session_messages(session_id: str, limit: int = Query(100, le=500)):
    async with get_session() as db:
        rows = (
            (
                await db.execute(
                    select(Message)
                    .where(Message.session_id == session_id)
                    .order_by(Message.created_at.asc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
    return [MessageOut.model_validate(r) for r in rows]


@router.post("/sessions/{session_id}/takeover")
async def takeover(session_id: str, body: TakeoverRequest):
    return await chat_service.takeover(session_id, body.operator, body.note)


@router.post("/sessions/{session_id}/release")
async def release(session_id: str, body: TakeoverRequest):
    return await chat_service.release(session_id, body.operator)


@router.post("/sessions/{session_id}/human-reply")
async def human_reply(session_id: str, body: TakeoverReplyRequest):
    return await chat_service.human_reply(session_id, body.operator, body.message)


@router.post("/tickets", response_model=TicketOut)
async def api_create_ticket(body: TicketCreate):
    tid = await create_ticket(
        session_id=body.session_id,
        tenant_id=body.tenant_id,
        title=body.title,
        description=body.description,
        category=body.category,
        priority=body.priority,
    )
    async with get_session() as db:
        row = (await db.execute(select(Ticket).where(Ticket.id == tid))).scalar_one()
    return TicketOut.model_validate(row)


@router.get("/tickets", response_model=List[TicketOut])
async def api_list_tickets(
    tenant_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
):
    rows = await list_tickets(tenant_id=tenant_id, status=status, limit=limit)
    return [TicketOut.model_validate(r) for r in rows]


@router.post("/kb/upload")
async def kb_upload(
    tenant_id: str = Form(default=settings.default_tenant_id),
    file: UploadFile = File(...),
):
    text = (await file.read()).decode("utf-8", errors="ignore")
    n = await kb.add_document(tenant_id, text, source=file.filename or "upload")
    return {"ok": True, "chunks": n}


@router.post("/kb/text")
async def kb_text(tenant_id: str = Form(...), text: str = Form(...), source: str = Form("manual")):
    n = await kb.add_document(tenant_id, text, source=source)
    return {"ok": True, "chunks": n}


@router.post("/kb/import-defaults")
async def kb_import_defaults(tenant_id: str = Form(default=settings.default_tenant_id)):
    n = await kb.import_directory(tenant_id, settings.knowledge_base_dir)
    return {"ok": True, "chunks": n}


@router.get("/stats", response_model=StatsOut)
async def stats(tenant_id: Optional[str] = None) -> StatsOut:
    async with get_session() as db:
        sess_filter = []
        if tenant_id:
            sess_filter.append(DBSession.tenant_id == tenant_id)
        total = await db.scalar(select(func.count(DBSession.id)).where(*sess_filter))
        active = await db.scalar(
            select(func.count(DBSession.id)).where(DBSession.status == "active", *sess_filter)
        )
        closed = await db.scalar(
            select(func.count(DBSession.id)).where(DBSession.status == "closed", *sess_filter)
        )
        takeover_n = await db.scalar(
            select(func.count(DBSession.id)).where(DBSession.status == "takeover", *sess_filter)
        )
        msgs = await db.scalar(select(func.count(Message.id)))
        tk_filter = []
        if tenant_id:
            tk_filter.append(Ticket.tenant_id == tenant_id)
        tickets_total = await db.scalar(select(func.count(Ticket.id)).where(*tk_filter))
        tickets_open = await db.scalar(
            select(func.count(Ticket.id)).where(Ticket.status == "open", *tk_filter)
        )
    return StatsOut(
        total_sessions=int(total or 0),
        active_sessions=int(active or 0),
        closed_sessions=int(closed or 0),
        takeover_sessions=int(takeover_n or 0),
        total_messages=int(msgs or 0),
        total_tickets=int(tickets_total or 0),
        open_tickets=int(tickets_open or 0),
    )
