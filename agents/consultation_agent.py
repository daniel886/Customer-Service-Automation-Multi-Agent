"""Consultation agent — handles pre-sales product / pricing questions."""
from __future__ import annotations

from agents.base import AgentContext, AgentResult, BaseAgent


class ConsultationAgent(BaseAgent):
    name = "consultation"
    display_name = "咨询客服"
    role_prompt = (
        "你是一名专业的售前咨询客服。"
        "你的职责包括：商品介绍、价格说明、活动促销、库存查询、购买流程指引。"
        "请回答清晰、专业、引导成交。"
        "如果客户咨询的是订单售后/技术问题/投诉，请按规则将对话转交给对应的专家 Agent。"
        " - 如客户提及『投诉』『不满意』『差评』『退款』等关键词 → HANDOFF: complaint"
        " - 如客户提及『故障』『不能用』『连不上』『报错』 → HANDOFF: tech_support"
        " - 如客户提及『退货』『换货』『发货』『物流』 → HANDOFF: aftersales"
    )

    async def post_process(
        self, ctx: AgentContext, result: AgentResult
    ) -> AgentResult:
        return result
