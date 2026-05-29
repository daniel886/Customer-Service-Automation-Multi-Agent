"""Tools package.

`kb` (Chroma vector store) is imported lazily so that lightweight
modules such as `tools.order_lookup` and `tools.ticket` can be used
without pulling chromadb / sentence-transformers into the import graph.
"""
from tools.order_lookup import lookup_order
from tools.ticket import create_ticket, list_tickets, update_ticket_status


def __getattr__(name):  # pragma: no cover - lazy import shim
    if name in ("kb", "KnowledgeBase"):
        from tools import knowledge_base as _kb
        return getattr(_kb, name)
    raise AttributeError(name)


__all__ = [
    "kb",
    "KnowledgeBase",
    "lookup_order",
    "create_ticket",
    "list_tickets",
    "update_ticket_status",
]
