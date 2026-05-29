"""ChatService business logic: ticket auto-creation, multi-tenant isolation,
hand-off mechanics, route-chain recording.
"""
import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/test_svc.db")


@pytest.fixture(scope="module", autouse=True)
def _stub_llm():
    from agents import base as base_mod

    async def fake(self, ctx):
        # Complaint agent appends a system note + creates a ticket via post_process.
        text = ctx.user_message
        if self.name == "complaint":
            return base_mod.AgentResult(
                agent_name="complaint",
                reply="非常抱歉给您带来不便。我们会尽快处理。",
                suggest_human_takeover="升级" in text,
            )
        return base_mod.AgentResult(agent_name=self.name, reply=f"[{self.name}] OK")

    # Use a LangChain-free run that goes through post_process to keep ticket
    async def a_run(self, ctx):
        await self.pre_process(ctx)
        result = await fake(self, ctx)
        return await self.post_process(ctx, result)

    orig = base_mod.BaseAgent.a_run
    base_mod.BaseAgent.a_run = a_run
    yield
    base_mod.BaseAgent.a_run = orig


@pytest.fixture(scope="module")
def client():
    from main import app
    with TestClient(app) as c:
        yield c


def test_complaint_creates_ticket(client):
    r = client.post(
        "/chat",
        json={"message": "我要投诉，发货太慢", "channel": "web"},
    )
    assert r.status_code == 200
    sid = r.json()["session_id"]
    # Expect ticket created
    tickets = client.get("/tickets").json()
    assert any(t["session_id"] == sid and t["category"] == "complaint" for t in tickets), tickets


def test_complaint_with_escalation(client):
    r = client.post(
        "/chat",
        json={"message": "我要投诉并升级到主管！", "channel": "web"},
    )
    data = r.json()
    assert data["handoff_to_human"] is True
    sid = data["session_id"]
    sess = client.get(f"/sessions/{sid}").json()
    assert sess["status"] == "takeover"
    assert sess["human_takeover"] == 1


def test_multi_tenant_isolation(client):
    r1 = client.post(
        "/chat",
        json={"message": "你好 A", "channel": "web", "tenant_id": "tenant_A"},
    )
    r2 = client.post(
        "/chat",
        json={"message": "你好 B", "channel": "web", "tenant_id": "tenant_B"},
    )
    s_a = client.get("/sessions?tenant_id=tenant_A").json()
    s_b = client.get("/sessions?tenant_id=tenant_B").json()
    assert all(s["tenant_id"] == "tenant_A" for s in s_a)
    assert all(s["tenant_id"] == "tenant_B" for s in s_b)
    assert {x["id"] for x in s_a}.isdisjoint({x["id"] for x in s_b})


def test_route_chain_recorded(client):
    r = client.post(
        "/chat",
        json={"message": "查询订单 20240519002 物流", "channel": "web"},
    )
    data = r.json()
    assert "aftersales" in data["routed_to"]
