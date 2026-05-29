"""Conversation memory management with persistence."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from core.logger import logger


@dataclass
class MemoryEntry:
    role: str  # user | assistant | system | agent
    content: str
    agent_name: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "agent_name": self.agent_name,
            "created_at": self.created_at.isoformat(),
        }


class ConversationMemory:
    """In-process LRU style conversation memory.

    Persistent storage is handled by the Database layer; this class
    holds the hot, in-memory recent context for fast LLM look-ups.
    """

    def __init__(self, max_messages: int = 30):
        self.max_messages = max_messages
        self._sessions: Dict[str, List[MemoryEntry]] = {}
        self._lock = asyncio.Lock()

    async def append(self, session_id: str, entry: MemoryEntry) -> None:
        async with self._lock:
            buf = self._sessions.setdefault(session_id, [])
            buf.append(entry)
            if len(buf) > self.max_messages:
                self._sessions[session_id] = buf[-self.max_messages :]

    async def get(self, session_id: str) -> List[MemoryEntry]:
        async with self._lock:
            return list(self._sessions.get(session_id, []))

    async def clear(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)
            logger.debug(f"Cleared memory for session={session_id}")

    async def render_for_llm(self, session_id: str) -> List[dict]:
        """Return OpenAI-style chat messages list."""
        msgs = await self.get(session_id)
        return [{"role": m.role if m.role in ("user", "assistant", "system") else "assistant",
                 "content": m.content} for m in msgs]


memory = ConversationMemory()
