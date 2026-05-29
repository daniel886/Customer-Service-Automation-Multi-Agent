"""Iteration 9: WebSocket end-to-end (init -> message -> agent reply)."""
import json
import os

import pytest

os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/test_ws.db")
os.environ.setdefault("TEST_MODE", "1")
os.environ.setdefault("EMAIL_ENABLED", "false")


def test_websocket_init_and_message(monkeypatch):
    """Patch the workflow runner so the WS does not hit OpenAI."""
    from agents import base as base_mod

    async def fake_run(self, ctx):
        return base_mod.AgentResult(
            agent_name="consultation",
            reply="你好，我是咨询助手。",
        )

    monkeypatch.setattr(base_mod.BaseAgent, "a_run", fake_run)

    from fastapi.testclient import TestClient
    import main as main_module

    with TestClient(main_module.app) as client:
        with client.websocket_connect("/ws/chat") as ws:
            ws.send_text(json.dumps({
                "type": "init",
                "tenant_id": "default",
                "customer_name": "Tester",
            }))
            ack = json.loads(ws.receive_text())
            assert ack["type"] == "ack"
            assert ack["session_id"]

            ws.send_text(json.dumps({"type": "message", "content": "你好"}))
            reply = json.loads(ws.receive_text())
            assert reply["type"] == "agent"
            assert reply["agent_name"] == "consultation"
            assert "咨询" in reply["content"]
            assert reply["handoff_to_human"] is False


def test_websocket_message_before_init_returns_error():
    from fastapi.testclient import TestClient
    import main as main_module

    with TestClient(main_module.app) as client:
        with client.websocket_connect("/ws/chat") as ws:
            ws.send_text(json.dumps({"type": "message", "content": "hi"}))
            data = json.loads(ws.receive_text())
            assert data["type"] == "error"
            assert "init" in data["message"]


def test_websocket_invalid_json_returns_error():
    from fastapi.testclient import TestClient
    import main as main_module

    with TestClient(main_module.app) as client:
        with client.websocket_connect("/ws/chat") as ws:
            ws.send_text("not json {{{")
            data = json.loads(ws.receive_text())
            assert data["type"] == "error"
