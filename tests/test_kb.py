"""Iteration 7: knowledge base RAG roundtrip + tenant isolation."""
import os

import pytest

os.environ.setdefault("OPENAI_API_KEY", "")  # force dummy embedder fallback
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/test_kb.db")
os.environ.setdefault("TEST_MODE", "1")


@pytest.mark.asyncio
async def test_kb_add_and_query():
    from tools.knowledge_base import KnowledgeBase

    kb = KnowledgeBase()
    # Force offline embedder so we don't hit OpenAI in tests
    kb._embedder = None

    await kb.reset("rag_t1")
    n = await kb.add_document(
        tenant_id="rag_t1",
        text=(
            "本店退货政策：商品签收后 7 天内可申请无理由退货。"
            "退款将在原支付渠道返还，3-5 个工作日到账。"
            "客服电话 400-123-4567。营业时间 9:00-21:00。"
        ),
        source="policy.md",
    )
    assert n >= 1
    hits = await kb.query("rag_t1", "退货多少天", top_k=3)
    assert isinstance(hits, list)
    assert len(hits) >= 1
    assert all("text" in h and "metadata" in h for h in hits)


@pytest.mark.asyncio
async def test_kb_tenant_isolation():
    from tools.knowledge_base import KnowledgeBase

    kb = KnowledgeBase()
    kb._embedder = None

    await kb.reset("rag_a")
    await kb.reset("rag_b")
    await kb.add_document("rag_a", "A 租户专属文档：苹果。", source="a.md")
    await kb.add_document("rag_b", "B 租户专属文档：香蕉。", source="b.md")

    a_hits = await kb.query("rag_a", "水果", top_k=4)
    b_hits = await kb.query("rag_b", "水果", top_k=4)

    a_text = " ".join(h["text"] for h in a_hits)
    b_text = " ".join(h["text"] for h in b_hits)

    assert "苹果" in a_text
    assert "香蕉" not in a_text
    assert "香蕉" in b_text
    assert "苹果" not in b_text


@pytest.mark.asyncio
async def test_kb_empty_collection_returns_empty():
    from tools.knowledge_base import KnowledgeBase

    kb = KnowledgeBase()
    kb._embedder = None
    await kb.reset("rag_empty")
    out = await kb.query("rag_empty", "anything", top_k=3)
    assert out == []
