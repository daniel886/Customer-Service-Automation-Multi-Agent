"""High-level chat orchestrator: persists messages, runs LangGraph workflow,
manages human-takeover, and broadcasts events.

File-storage policy
-------------------
All persistence is local: SQLite + Chroma both live under ``PROJECT_ROOT/data``
(see ``core.config.Settings.ensure_dirs``). The orchestrator never waits on
external services for permission grants:

* The DB directory is auto-created with mode ``0755`` at import time.
* Lazy imports of LangGraph/OpenAI keep cold-start cheap and side-effect free.
* Workflow / I/O failures degrade gracefully to a templated reply instead of
  pinning the request thread on a blocking permission error.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from sqlalchemy import select

from agents.base import AgentResult
from core.config import PROJECT_ROOT, settings
from core.logger import logger
from core.memory import MemoryEntry, memory
from models.database import Message, Session as DBSession, get_session


def _ensure_local_storage() -> None:
    """Idempotent guarantee that all local storage paths are writable."""
    data_dir = PROJECT_ROOT / "data"
    logs_dir = PROJECT_ROOT / "logs"
    for d in (data_dir, logs_dir, Path(settings.chroma_persist_dir)):
        try:
            d.mkdir(parents=True, exist_ok=True)
            os.chmod(d, 0o755)
        except (PermissionError, OSError) as exc:
            logger.debug(f"local storage prep skipped for {d}: {exc}")


_ensure_local_storage()


class ChatService:
    """Top-level façade used by HTTP / WS / channel handlers."""

    async def get_or_create_session(
        self,
        session_id: Optional[str],
        tenant_id: Optional[str],
        channel: str,
        customer_id: Optional[str],
        customer_name: Optional[str],
    ) -> DBSession:
        tenant_id = tenant_id or settings.default_tenant_id
        async with get_session() as db:
            if session_id:
                row = (
                    await db.execute(select(DBSession).where(DBSession.id == session_id))
                ).scalar_one_or_none()
                if row is not None:
                    return row
            new_id = session_id or f"S-{uuid.uuid4().hex[:12]}"
            row = DBSession(
                id=new_id,
                tenant_id=tenant_id,
                channel=channel,
                customer_id=customer_id,
                customer_name=customer_name,
                status="active",
            )
            db.add(row)
            await db.flush()
            await db.refresh(row)
            return row

    async def list_history(self, session_id: str, limit: int = 20) -> List[dict]:
        async with get_session() as db:
            rows = (
                (
                    await db.execute(
                        select(Message)
                        .where(Message.session_id == session_id)
                        .order_by(Message.created_at.desc())
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
        rows = list(reversed(rows))
        return [{"role": r.role, "content": r.content, "agent_name": r.agent_name} for r in rows]

    async def _persist_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agent_name: Optional[str] = None,
        meta: Optional[dict] = None,
    ) -> None:
        async with get_session() as db:
            db.add(
                Message(
                    session_id=session_id,
                    role=role,
                    content=content,
                    agent_name=agent_name,
                    meta=json.dumps(meta or {}, ensure_ascii=False),
                )
            )

    async def _update_session(
        self,
        session_id: str,
        *,
        current_agent: Optional[str] = None,
        status: Optional[str] = None,
        human_takeover: Optional[int] = None,
    ) -> None:
        async with get_session() as db:
            row = (
                await db.execute(select(DBSession).where(DBSession.id == session_id))
            ).scalar_one_or_none()
            if row is None:
                return
            if current_agent is not None:
                row.current_agent = current_agent
            if status is not None:
                row.status = status
            if human_takeover is not None:
                row.human_takeover = human_takeover
            row.updated_at = datetime.utcnow()

    async def handle_user_turn(
        self,
        *,
        message: str,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        channel: str = "web",
        customer_id: Optional[str] = None,
        customer_name: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        sess = await self.get_or_create_session(
            session_id, tenant_id, channel, customer_id, customer_name
        )

        # If the session is in human-takeover mode, do not invoke any agent.
        if sess.human_takeover == 1 or sess.status == "takeover":
            await self._persist_message(sess.id, "user", message)
            await memory.append(sess.id, MemoryEntry(role="user", content=message))
            return {
                "session_id": sess.id,
                "agent_name": "human-pending",
                "reply": "您的问题已提交人工客服，请稍候 (人工客服会尽快回复您)。",
                "routed_to": [],
                "handoff_to_human": True,
                "metadata": {"awaiting_human": True},
            }

        # Persist user message
        await self._persist_message(sess.id, "user", message)
        await memory.append(sess.id, MemoryEntry(role="user", content=message))

        # Build history for the workflow
        history = await self.list_history(sess.id, limit=12)

        # Run LangGraph workflow (lazy import keeps cold start cheap)
        try:
            from workflows.graph import run_workflow

            result: AgentResult = await run_workflow(
                session_id=sess.id,
                tenant_id=sess.tenant_id,
                user_message=message,
                history=history,
                metadata=metadata,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"workflow error: {exc}")
            result = AgentResult(
                agent_name="system",
                reply="系统繁忙，正在为您转接人工客服。",
                suggest_human_takeover=True,
            )

        # Determine takeover
        handoff_to_human = result.suggest_human_takeover
        new_status = "takeover" if handoff_to_human else "active"

        await self._persist_message(
            sess.id,
            role="assistant",
            content=result.reply,
            agent_name=result.agent_name,
            meta={"actions": result.actions},
        )
        await memory.append(
            sess.id,
            MemoryEntry(role="assistant", content=result.reply, agent_name=result.agent_name),
        )
        await self._update_session(
            sess.id,
            current_agent=result.agent_name,
            status=new_status,
            human_takeover=1 if handoff_to_human else 0,
        )

        chain: list[str] = []
        for a in result.actions:
            if a.get("type") == "route_chain":
                chain = a.get("chain") or []

        return {
            "session_id": sess.id,
            "agent_name": result.agent_name,
            "reply": result.reply,
            "routed_to": chain,
            "handoff_to_human": handoff_to_human,
            "metadata": {"actions": result.actions},
        }

    async def human_reply(self, session_id: str, operator: str, message: str) -> dict:
        """Send a reply on behalf of a human agent."""
        await self._persist_message(
            session_id,
            role="human-agent",
            content=message,
            agent_name=operator,
        )
        await memory.append(
            session_id, MemoryEntry(role="assistant", content=message, agent_name=operator)
        )
        await self._update_session(session_id, current_agent=f"human:{operator}")
        return {"session_id": session_id, "operator": operator, "ok": True}

    async def takeover(self, session_id: str, operator: str, note: Optional[str]) -> dict:
        await self._update_session(
            session_id, status="takeover", human_takeover=1, current_agent=f"human:{operator}"
        )
        if note:
            await self._persist_message(
                session_id,
                role="system",
                content=f"[人工接管] 操作员={operator}: {note}",
            )
        logger.info(f"Session {session_id} taken over by {operator}")
        return {"session_id": session_id, "operator": operator, "ok": True}

    async def release(self, session_id: str, operator: str) -> dict:
        await self._update_session(session_id, status="active", human_takeover=0)
        await self._persist_message(
            session_id, role="system", content=f"[人工释放] 操作员={operator}"
        )
        logger.info(f"Session {session_id} released by {operator}")
        return {"session_id": session_id, "operator": operator, "ok": True}


chat_service = ChatService()
