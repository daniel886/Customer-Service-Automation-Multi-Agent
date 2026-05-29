"""Verify the FastAPI app boots and registers all expected routes."""
import os

import pytest

os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/test.db")


@pytest.fixture(scope="module")
def app():
    from main import app as _app
    return _app


def test_app_metadata(app):
    assert app.title.startswith("Customer-Service")
    assert app.version


def test_routes_registered(app):
    paths = {r.path for r in app.routes}
    expected = {
        "/health",
        "/chat",
        "/sessions",
        "/sessions/{session_id}",
        "/sessions/{session_id}/messages",
        "/sessions/{session_id}/takeover",
        "/sessions/{session_id}/release",
        "/sessions/{session_id}/human-reply",
        "/tickets",
        "/kb/upload",
        "/kb/text",
        "/kb/import-defaults",
        "/stats",
        "/ws/chat",
        "/admin/login",
        "/admin/me",
        "/integrations/wechat/callback",
        "/",
        "/admin",
        "/static",
    }
    missing = expected - paths
    assert not missing, f"missing routes: {missing}"


def test_openapi_schema(app):
    schema = app.openapi()
    assert "openapi" in schema
    assert "/chat" in schema["paths"]
