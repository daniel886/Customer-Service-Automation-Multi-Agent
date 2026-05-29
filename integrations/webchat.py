"""Web chat integration: thin compatibility wrapper around the WebSocket router.

Exposes the static admin / chat HTML pages via FastAPI's StaticFiles in
`main.py`. This module currently re-exports the websocket router for
clarity of `integrations` package layout.
"""
from __future__ import annotations

from api.websocket import router as websocket_router  # noqa: F401

__all__ = ["websocket_router"]
