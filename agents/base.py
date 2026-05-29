"""Base classes for the four specialized agents.

We use LangChain's ChatOpenAI for LLM calls, following the AutoGen
"assistant agent" interaction style. The base class provides:

* Common LLM wiring
* RAG retrieval helper
* AutoGen-style `a_run` async entry point
* Hand-off / collaboration hooks
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from core.config import settings
from core.logger import logger


@dataclass
class AgentContext:
    """State carried through one user turn."""

    session_id: str
    tenant_id: str
    user_message: str
    history: List[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    rag_snippets: List[str] = field(default_factory=list)


@dataclass
class AgentResult:
    agent_name: str
    reply: str
    handoff_to: Optional[str] = None  # next agent name
    suggest_human_takeover: bool = False
    actions: List[dict] = field(default_factory=list)  # e.g., {"type": "create_ticket", ...}


class BaseAgent(abc.ABC):
    """Abstract base for all customer-service agents."""

    name: str = "base"
    display_name: str = "Base Agent"
    role_prompt: str = "You are a generic customer service assistant."
    use_rag: bool = True

    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            api_key=settings.openai_api_key or "sk-placeholder",
            base_url=settings.openai_base_url,
            timeout=60,
            max_retries=2,
        )

    # ----- Hooks subclasses may override -----

    async def pre_process(self, ctx: AgentContext) -> None:  # noqa: D401
        """Run before the LLM call. Default: load RAG snippets."""
        if self.use_rag:
            try:
                from tools.knowledge_base import kb  # lazy import
                hits = await kb.query(ctx.tenant_id, ctx.user_message, top_k=4)
                ctx.rag_snippets = [h["text"] for h in hits]
                if hits:
                    logger.debug(f"[{self.name}] RAG hits={len(hits)}")
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[{self.name}] RAG query failed: {exc}")

    async def post_process(self, ctx: AgentContext, result: AgentResult) -> AgentResult:
        return result

    # ----- Main entry point -----

    async def a_run(self, ctx: AgentContext) -> AgentResult:
        await self.pre_process(ctx)
        messages = self._build_messages(ctx)
        try:
            ai_msg = await self.llm.ainvoke(messages)
            reply = (ai_msg.content if isinstance(ai_msg, AIMessage) else str(ai_msg)) or ""
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"[{self.name}] LLM call failed: {exc}")
            reply = self._fallback_reply()

        result = await self._postprocess_reply(ctx, reply)
        result = await self.post_process(ctx, result)
        return result

    # ----- Helpers -----

    def _build_messages(self, ctx: AgentContext):
        sys_prompt = self.role_prompt
        if ctx.rag_snippets:
            sys_prompt += "\n\n以下是相关知识片段，请参考但不要照抄：\n"
            for i, s in enumerate(ctx.rag_snippets, 1):
                sys_prompt += f"[{i}] {s}\n"
        sys_prompt += (
            "\n\n请用简洁、专业、亲切的中文回复客户。"
            "如果不能完全解决问题，请明确说明并建议下一步。"
            "若问题超出你的职责范围，请在回复末尾输出一行 `HANDOFF: <agent_name>`。"
            "若需要人工客服介入，请在回复末尾输出 `HUMAN_TAKEOVER: yes`。"
        )

        msgs = [SystemMessage(content=sys_prompt)]
        for m in ctx.history[-12:]:
            role = m.get("role")
            content = m.get("content", "")
            if role == "user":
                msgs.append(HumanMessage(content=content))
            else:
                msgs.append(AIMessage(content=content))
        msgs.append(HumanMessage(content=ctx.user_message))
        return msgs

    async def _postprocess_reply(self, ctx: AgentContext, raw: str) -> AgentResult:
        handoff = None
        takeover = False
        clean_lines: List[str] = []

        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("HANDOFF:"):
                handoff = stripped.split(":", 1)[1].strip()
            elif stripped.upper().startswith("HUMAN_TAKEOVER:"):
                takeover = "yes" in stripped.lower() or "true" in stripped.lower()
            else:
                clean_lines.append(line)

        return AgentResult(
            agent_name=self.name,
            reply="\n".join(clean_lines).strip(),
            handoff_to=handoff,
            suggest_human_takeover=takeover,
        )

    def _fallback_reply(self) -> str:
        return (
            "非常抱歉，当前服务暂时遇到一些问题，正在为您转接人工客服。"
            "感谢您的耐心等待。"
        )
