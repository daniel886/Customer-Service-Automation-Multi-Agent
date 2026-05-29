"""Smoke tests that do not require an OpenAI API key."""
from __future__ import annotations

import asyncio
import os

import pytest

os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/test.db")

from workflows.router import route_intent  # noqa: E402
from tools.order_lookup import lookup_order  # noqa: E402
from models.database import init_db  # noqa: E402


def test_router_consultation():
    assert route_intent("这款手表多少钱？有活动吗？") == "consultation"


def test_router_complaint():
    assert route_intent("我要投诉，体验太差了") == "complaint"


def test_router_tech():
    assert route_intent("APP 登录不上，一直报错") == "tech_support"


def test_router_aftersales():
    assert route_intent("我的快递还没到，订单号 20240518001") == "aftersales"


@pytest.mark.asyncio
async def test_order_lookup():
    o = await lookup_order("20240518001")
    assert o is not None
    assert o["status"]


@pytest.mark.asyncio
async def test_init_db():
    await init_db()
