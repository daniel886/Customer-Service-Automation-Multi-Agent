"""Workflows package.

Note: `graph` and `run_workflow` import LangGraph/LangChain heavyweights, so
they are imported lazily on first use to keep `workflows.router` importable
in lightweight environments (e.g. CI smoke tests).
"""
from workflows.router import route_intent


def __getattr__(name):  # pragma: no cover - lazy import shim
    if name in ("build_graph", "run_workflow"):
        from workflows import graph as _graph
        return getattr(_graph, name)
    raise AttributeError(name)


__all__ = ["build_graph", "run_workflow", "route_intent"]
