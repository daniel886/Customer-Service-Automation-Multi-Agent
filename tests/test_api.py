"""HTTP API smoke tests using FastAPI TestClient.

LLM calls in agents are stubbed via monkeypatch so we can exercise
real DB persistence + workflow without an OpenAI key.
"""
import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/test_api.db")


@pytest.fixture(scope="module", autouse=True)
def _stub_llm():
    """Replace BaseAgent.a_run with a deterministic stub."""
    from agents import base as base_mod

    async def fake_a_run(self, ctx):
        # Echo the routing decision for visibility.
        text = ctx.user_message
        reply = f"[{self.name}] 您好，已收到：{text}"
        return base_mod.AgentResult(agent_name=self.name, reply=reply)

    orig = base_mod.BaseAgent.a_run
    base_mod.BaseAgent.a_run = fake_a_run
    yield
    base_mod.BaseAgent.a_run = orig


@pytest.fixture(scope="module")
def client():
    from main import app
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_chat_consultation(client):
    r = client.post(
        "/chat",
        json={"message": "你好，请介绍下智能手表 Pro", "channel": "web"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["agent_name"] == "consultation"
    assert "consultation" in data["reply"]
    assert data["session_id"]


def test_chat_complaint(client):
    r = client.post(
        "/chat",
        json={"message": "我要投诉，体验太差！", "channel": "web"},
    )
    assert r.status_code == 200
    assert r.json()["agent_name"] == "complaint"


def test_chat_techsupport(client):
    r = client.post(
        "/chat",
        json={"message": "App 登录不上，一直报错", "channel": "web"},
    )
    assert r.status_code == 200
    assert r.json()["agent_name"] == "tech_support"


def test_chat_aftersales(client):
    r = client.post(
        "/chat",
        json={"message": "查询订单 20240518001 的物流状态", "channel": "web"},
    )
    assert r.status_code == 200
    assert r.json()["agent_name"] == "aftersales"


def test_sessions_and_messages(client):
    r = client.post("/chat", json={"message": "再问一个问题", "channel": "web"})
    assert r.status_code == 200
    sid = r.json()["session_id"]
    r2 = client.get(f"/sessions/{sid}/messages")
    assert r2.status_code == 200
    msgs = r2.json()
    assert any(m["role"] == "user" for m in msgs)
    assert any(m["role"] == "assistant" for m in msgs)


def test_stats_endpoint(client):
    r = client.get("/stats")
    assert r.status_code == 200
    s = r.json()
    assert s["total_sessions"] >= 1
    assert s["total_messages"] >= 2
