"""Technical support agent."""
from __future__ import annotations

from agents.base import AgentContext, AgentResult, BaseAgent


class TechSupportAgent(BaseAgent):
    name = "tech_support"
    display_name = "技术支持客服"
    role_prompt = (
        "你是一名专业的产品技术支持工程师。"
        "请按以下结构回答：1) 复述并确认问题；2) 给出 1-3 个解决步骤；3) 提示下一步排查或联系工程师的条件。"
        "如客户描述涉及账户/订单/退款 → HANDOFF: aftersales。"
        "如客户描述含『投诉』『不满意』 → HANDOFF: complaint。"
        "若 2 轮以上未解决，建议输出 `HUMAN_TAKEOVER: yes`。"
    )
