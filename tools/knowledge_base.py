"""Chroma-based RAG knowledge base."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

from core.config import settings
from core.logger import logger


class KnowledgeBase:
    """Chroma vector store with OpenAI embeddings.

    The KB is segmented per-tenant by collection name:
        kb_<tenant_id>
    """

    def __init__(self) -> None:
        Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
        try:
            self._embedder = OpenAIEmbeddings(
                model=settings.openai_embedding_model,
                api_key=settings.openai_api_key or "sk-placeholder",
                base_url=settings.openai_base_url,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Falling back to dummy embedder: {exc}")
            self._embedder = None

        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=600, chunk_overlap=80, separators=["\n\n", "\n", "。", "！", "？", " "]
        )

    def _collection_name(self, tenant_id: str) -> str:
        return f"kb_{tenant_id or settings.default_tenant_id}"

    def _get_collection(self, tenant_id: str):
        return self._client.get_or_create_collection(
            name=self._collection_name(tenant_id),
            metadata={"hnsw:space": "cosine"},
        )

    async def _embed(self, texts: List[str]) -> List[List[float]]:
        if self._embedder is None:
            # Deterministic fallback for offline tests.
            return [[float((sum(ord(c) for c in t) % 97) / 97.0)] * 8 for t in texts]
        return await asyncio.to_thread(self._embedder.embed_documents, texts)

    async def add_document(
        self,
        tenant_id: str,
        text: str,
        source: str = "manual",
        metadata: Optional[dict] = None,
    ) -> int:
        """Chunk and add a document to the tenant's KB. Returns chunk count."""
        chunks = self._splitter.split_text(text)
        if not chunks:
            return 0
        embeddings = await self._embed(chunks)
        col = self._get_collection(tenant_id)
        ids = [f"{source}-{tenant_id}-{i}-{abs(hash(c)) % (10 ** 10)}" for i, c in enumerate(chunks)]
        metas = [{"source": source, "tenant_id": tenant_id, **(metadata or {})} for _ in chunks]
        col.add(documents=chunks, embeddings=embeddings, metadatas=metas, ids=ids)
        logger.info(f"KB[{tenant_id}] added {len(chunks)} chunks from {source}")
        return len(chunks)

    async def query(
        self, tenant_id: str, question: str, top_k: int = 4
    ) -> List[dict]:
        col = self._get_collection(tenant_id)
        if col.count() == 0:
            return []
        emb = (await self._embed([question]))[0]
        res = col.query(query_embeddings=[emb], n_results=top_k)
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        scores = res.get("distances", [[]])[0]
        return [
            {"text": d, "metadata": m, "score": float(s)}
            for d, m, s in zip(docs, metas, scores)
        ]

    async def import_directory(self, tenant_id: str, directory: str) -> int:
        """Bulk import .md/.txt files from a directory. Returns total chunks."""
        path = Path(directory)
        if not path.exists():
            logger.warning(f"Knowledge base directory not found: {directory}")
            return 0
        total = 0
        for fp in path.rglob("*"):
            if fp.is_file() and fp.suffix.lower() in {".md", ".txt"}:
                try:
                    text = fp.read_text(encoding="utf-8")
                    total += await self.add_document(tenant_id, text, source=fp.name)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(f"Failed to import {fp}: {exc}")
        logger.info(f"KB[{tenant_id}] imported {total} chunks from {directory}")
        return total

    async def reset(self, tenant_id: str) -> None:
        try:
            self._client.delete_collection(self._collection_name(tenant_id))
        except Exception:  # noqa: BLE001
            pass


kb = KnowledgeBase()
