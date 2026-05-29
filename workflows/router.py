"""Lightweight intent router.

Used by the LangGraph supervisor node to choose which specialist
agent should handle the current turn before falling back to the LLM.
"""
from __future__ import annotations

import re
from typing import Literal

AgentName = Literal["consultation", "complaint", "tech_support", "aftersales"]


_RULES: list[tuple[re.Pattern[str], AgentName]] = [
    (re.compile(r"投诉|不满意|差评|要求.*主管|曝光|315|工商|315投诉", re.I), "complaint"),
    (re.compile(r"故障|无法|不能用|连不上|报错|蓝屏|黑屏|死机|崩溃|登录不上", re.I), "tech_support"),
    (re.compile(r"退货|换货|发货|物流|快递|运单|订单号|退款|发票|签收", re.I), "aftersales"),
    (re.compile(r"价格|多少钱|促销|活动|库存|什么时候.*上新|怎么买|介绍一下", re.I), "consultation"),
]


def route_intent(text: str) -> AgentName:
    """Rule-based intent routing. Defaults to `consultation`."""
    if not text:
        return "consultation"
    for pattern, agent in _RULES:
        if pattern.search(text):
            return agent
    return "consultation"
