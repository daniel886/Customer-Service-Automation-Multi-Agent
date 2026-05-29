"""Complaint handling agent."""
from __future__ import annotations

from agents.base import AgentContext, AgentResult, BaseAgent
from core.logger import logger
from tools.ticket import create_ticket


class ComplaintAgent(BaseAgent):
    name = "complaint"
    display_name = "投诉处理客服"
    role_prompt = (
        "你是一名经验丰富的投诉处理专员。"
        "请始终保持同理心，认真倾听客户的不满，先安抚情绪，再分析原因，并给出明确的处理方案与时间承诺。"
        "如果客户情绪激烈、连续 2 次表达不满，或要求『升级』『主管』『投诉至工商』等，请输出 `HUMAN_TAKEOVER: yes`。"
        "你需要在回复中包含三段：1) 致歉与共情，2) 处理方案与时间，3) 后续跟进承诺。"
    )

    async def post_process(
        self, ctx: AgentContext, result: AgentResult
    ) -> AgentResult:
        # Always create a ticket for complaints (tracked & followed-up)
        try:
            ticket_id = await create_ticket(
                session_id=ctx.session_id,
                tenant_id=ctx.tenant_id,
                title=f"客户投诉：{ctx.user_message[:30]}",
                description=ctx.user_message,
                category="complaint",
                priority="high" if result.suggest_human_takeover else "normal",
            )
            result.actions.append({"type": "create_ticket", "ticket_id": ticket_id})
            result.reply += f"\n\n（系统提示：已为您创建投诉工单 {ticket_id}，专员将在 24 小时内联系您。）"
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Complaint ticket creation failed: {exc}")
        return result
