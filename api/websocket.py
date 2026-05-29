"""WebSocket endpoint for the embedded web chat widget.

Protocol (JSON):
    Client -> Server:
        { "type": "init", "session_id": "...", "tenant_id": "...", "customer_name": "..." }
        { "type": "message", "content": "..." }
    Server -> Client:
        { "type": "ack", "session_id": "..." }
        { "type": "agent", "agent_name": "...", "content": "...", "handoff_to_human": false }
        { "type": "human", "operator": "...", "content": "..." }
        { "type": "system", "content": "..." }
"""
from __future__ import annotations

import asyncio
import json
from typing import Dict, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.chat_service import chat_service
from core.config import settings
from core.logger import logger

router = APIRouter()


class WSManager:
    """Track per-session client websockets so admin replies can be pushed."""

    def __init__(self) -> None:
        self._clients: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def attach(self, session_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.setdefault(session_id, set()).add(ws)

    async def detach(self, session_id: str, ws: WebSocket) -> None:
        async with self._lock:
            s = self._clients.get(session_id)
            if s and ws in s:
                s.remove(ws)
                if not s:
                    self._clients.pop(session_id, None)

    async def broadcast(self, session_id: str, payload: dict) -> None:
        dead = []
        async with self._lock:
            targets = list(self._clients.get(session_id, []))
        for ws in targets:
            try:
                await ws.send_text(json.dumps(payload, ensure_ascii=False))
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            await self.detach(session_id, ws)


ws_manager = WSManager()


@router.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket) -> None:
    await ws.accept()
    session_id: Optional[str] = None
    tenant_id: str = settings.default_tenant_id
    customer_name: Optional[str] = None

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({"type": "error", "message": "invalid JSON"}))
                continue

            mtype = data.get("type")
            if mtype == "init":
                session_id = data.get("session_id") or None
                tenant_id = data.get("tenant_id") or settings.default_tenant_id
                customer_name = data.get("customer_name") or None
                # Touch / create session
                sess = await chat_service.get_or_create_session(
                    session_id=session_id,
                    tenant_id=tenant_id,
                    channel="web",
                    customer_id=data.get("customer_id"),
                    customer_name=customer_name,
                )
                session_id = sess.id
                await ws_manager.attach(session_id, ws)
                await ws.send_text(json.dumps({"type": "ack", "session_id": session_id}))
                continue

            if mtype == "message":
                if not session_id:
                    await ws.send_text(
                        json.dumps({"type": "error", "message": "send 'init' first"})
                    )
                    continue
                content = (data.get("content") or "").strip()
                if not content:
                    continue
                resp = await chat_service.handle_user_turn(
                    message=content,
                    session_id=session_id,
                    tenant_id=tenant_id,
                    channel="web",
                    customer_name=customer_name,
                )
                payload = {
                    "type": "agent",
                    "agent_name": resp["agent_name"],
                    "content": resp["reply"],
                    "handoff_to_human": resp["handoff_to_human"],
                    "routed_to": resp["routed_to"],
                }
                await ws_manager.broadcast(session_id, payload)
                continue

            await ws.send_text(json.dumps({"type": "error", "message": f"unknown type: {mtype}"}))

    except WebSocketDisconnect:
        if session_id:
            await ws_manager.detach(session_id, ws)
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"ws error: {exc}")
        if session_id:
            await ws_manager.detach(session_id, ws)
