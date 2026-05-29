"""Mock order lookup tool. Replace with real ERP integration in production."""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Optional

from core.logger import logger


# Simulated order DB for demonstration purposes.
_DEMO_ORDERS: dict[str, dict] = {
    "20240518001": {
        "order_id": "20240518001",
        "customer": "张先生",
        "product": "智能手表 Pro",
        "amount": 1299.0,
        "status": "已发货",
        "tracking_no": "SF1234567890",
        "carrier": "顺丰",
        "created_at": (datetime.utcnow() - timedelta(days=2)).isoformat(),
        "expected_delivery": (datetime.utcnow() + timedelta(days=1)).isoformat(),
    },
    "20240519002": {
        "order_id": "20240519002",
        "customer": "李女士",
        "product": "无线耳机 Air",
        "amount": 499.0,
        "status": "申请退货",
        "tracking_no": None,
        "carrier": None,
        "created_at": (datetime.utcnow() - timedelta(days=10)).isoformat(),
        "expected_delivery": None,
    },
}


async def lookup_order(order_id: str) -> Optional[dict]:
    """Return order info or None.

    For the demo we use a fixed dataset; for real deployments,
    connect to the customer's ERP via REST/GraphQL.
    """
    logger.debug(f"Looking up order {order_id}")
    if order_id in _DEMO_ORDERS:
        return _DEMO_ORDERS[order_id]
    # Generate a deterministic mock for unknown ids
    if order_id.isdigit() and len(order_id) >= 6:
        return {
            "order_id": order_id,
            "customer": "未知客户",
            "product": "通用商品",
            "amount": round(random.uniform(50, 999), 2),
            "status": random.choice(["待付款", "待发货", "已发货", "已签收"]),
            "tracking_no": "SF" + order_id[-10:].rjust(10, "0"),
            "carrier": "顺丰",
            "created_at": datetime.utcnow().isoformat(),
            "expected_delivery": (datetime.utcnow() + timedelta(days=2)).isoformat(),
        }
    return None
