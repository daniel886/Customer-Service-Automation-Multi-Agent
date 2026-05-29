"""After-sales agent: orders, shipping, returns, refunds."""
from __future__ import annotations

import re

from agents.base import AgentContext, AgentResult, BaseAgent
from core.logger import logger
from tools.order_lookup import lookup_order


_ORDER_RE = re.compile(r"\b\d{8,20}\b")


class AfterSalesAgent(BaseAgent):
    name = "aftersales"
    display_name = "售后客服"
    role_prompt = (
        "你是一名售后客服，处理订单查询、物流追踪、退货换货、发票问题等。"
        "如果客户提供了订单号，请基于工具返回的订单数据回答。"
        "请明确列出：订单号、状态、预计送达、下一步建议。"
        "若客户要求『投诉』，请 HANDOFF: complaint。"
    )

    async def pre_process(self, ctx: AgentContext) -> None:
        await super().pre_process(ctx)
        # Detect a potential order id and inject into the prompt
        m = _ORDER_RE.search(ctx.user_message)
        if m:
            order_id = m.group(0)
            try:
                order = await lookup_order(order_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Order lookup failed: {exc}")
                order = None
            if order:
                ctx.metadata["order"] = order
                snippet = (
                    f"【订单数据】订单号 {order['order_id']}，客户 {order['customer']}，"
                    f"商品 {order['product']}，金额 ¥{order['amount']}，"
                    f"状态 {order['status']}，运单号 {order.get('tracking_no') or '无'}，"
                    f"承运商 {order.get('carrier') or '无'}，"
                    f"预计送达 {order.get('expected_delivery') or '未知'}。"
                )
                ctx.rag_snippets.insert(0, snippet)
