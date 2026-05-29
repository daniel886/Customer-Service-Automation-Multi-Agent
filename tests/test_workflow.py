"""LangGraph workflow + hand-off behavior."""
import os
import asyncio

import pytest

os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/test_wf.db")


@pytest.mark.asyncio
async def test_handoff_consultation_to_aftersales(monkeypatch):
    """consultation -> aftersales hand-off via HANDOFF marker."""
    from agents import base as base_mod

    async def fake(self, ctx):
        if self.name == "consultation":
            return base_mod.AgentResult(
                agent_name="consultation",
                reply="先为您介绍商品",
                handoff_to="aftersales",
            )
        if self.name == "aftersales":
            return base_mod.AgentResult(
                agent_name="aftersales", reply="已为您查询订单",
            )
        return base_mod.AgentResult(agent_name=self.name, reply="ok")

    async def a_run(self, ctx):
        return await fake(self, ctx)

    monkeypatch.setattr(base_mod.BaseAgent, "a_run", a_run)

    # Re-import workflow after patch (graph module instantiates agents at import)
    from workflows.graph import run_workflow
    from models.database import init_db

    await init_db()
    result = await run_workflow(
        session_id="S-WF-1",
        tenant_id="default",
        user_message="先咨询，然后查订单 20240519002",
    )
    chain = next((a["chain"] for a in result.actions if a.get("type") == "route_chain"), [])
    assert "consultation" in chain
    assert "aftersales" in chain
    assert result.agent_name == "aftersales"


@pytest.mark.asyncio
async def test_handoff_max_hops(monkeypatch):
    """Loops between two agents must terminate within max hops."""
    from agents import base as base_mod

    async def loopy(self, ctx):
        target = "aftersales" if self.name == "consultation" else "consultation"
        return base_mod.AgentResult(
            agent_name=self.name, reply=f"from {self.name}", handoff_to=target,
        )

    async def a_run(self, ctx):
        return await loopy(self, ctx)

    monkeypatch.setattr(base_mod.BaseAgent, "a_run", a_run)

    from workflows.graph import run_workflow

    result = await run_workflow(
        session_id="S-WF-2", tenant_id="default", user_message="loop"
    )
    # Max 2 handoffs => chain length <= 3
    chain = next(a["chain"] for a in result.actions if a.get("type") == "route_chain")
    assert len(chain) <= 3, chain


def test_router_intent_extra_cases():
    from workflows.router import route_intent
    assert route_intent("空字符串场景") == "consultation"
    assert route_intent("") == "consultation"
    assert route_intent("我要 315 投诉") == "complaint"
    assert route_intent("产品多少钱啊") == "consultation"
    assert route_intent("我要退货啊") == "aftersales"
    assert route_intent("登录死机崩溃了") == "tech_support"
