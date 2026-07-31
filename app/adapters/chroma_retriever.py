"""Chroma-backed knowledge store (custom RAG, no LangChain).

Why Chroma: local, persistent, good enough for a curated policy corpus.
Why an adapter: swap embeddings / vector DB later without touching services.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol, Sequence

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from app.adapters.knowledge_loader import load_knowledge_documents
from app.schemas.retrieval import Citation, KnowledgeDocument


class DeterministicHashEmbedding(EmbeddingFunction[Documents]):
    """Tiny local embedding for tests — no model download, deterministic.

    Not for production quality retrieval; production uses Chroma's default ONNX EF.
    """

    def __init__(self, dim: int = 64):
        self.dim = dim

    @staticmethod
    def name() -> str:
        return "deterministic_hash"

    def __call__(self, input: Documents) -> Embeddings:
        vectors: Embeddings = []
        for text in input:
            vec = [0.0] * self.dim
            for token in text.lower().replace("|", " ").split():
                vec[hash(token) % self.dim] += 1.0
            # L2 normalize for cosine-ish behavior
            norm = sum(v * v for v in vec) ** 0.5 or 1.0
            vectors.append([v / norm for v in vec])
        return vectors


class KnowledgeRetriever(Protocol):
    def ingest(self, documents: Sequence[KnowledgeDocument], *, reset: bool = False) -> int: ...

    def query(self, query_text: str, *, n_results: int = 3) -> list[Citation]: ...


class ChromaKnowledgeStore:
    """Persistent Chroma collection over curated SAR policy docs."""

    def __init__(
        self,
        persist_dir: str | Path,
        collection_name: str = "sar_policy_knowledge",
        embedding_function: Optional[EmbeddingFunction] = None,
    ):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self._embedding_function = embedding_function
        self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        self._collection = self._get_or_create_collection()

    def _get_or_create_collection(self):
        kwargs = {"name": self.collection_name, "metadata": {"hnsw:space": "cosine"}}
        if self._embedding_function is not None:
            kwargs["embedding_function"] = self._embedding_function
        return self._client.get_or_create_collection(**kwargs)

    def reset(self) -> None:
        self._client.delete_collection(self.collection_name)
        self._collection = self._get_or_create_collection()

    def ingest(self, documents: Sequence[KnowledgeDocument], *, reset: bool = False) -> int:
        if reset:
            self.reset()
        if not documents:
            return 0

        ids = [doc.doc_id for doc in documents]
        # Embed title + keywords + body so typology terms are searchable
        texts = [f"{doc.title}\n{doc.keywords}\n{doc.text}" for doc in documents]
        metadatas = [
            {
                "title": doc.title,
                "source_path": doc.source_path,
                "keywords": doc.keywords,
                "typologies": ",".join(doc.typologies),
            }
            for doc in documents
        ]
        # Upsert so re-ingest is idempotent
        self._collection.upsert(ids=ids, documents=texts, metadatas=metadatas)
        return len(documents)

    def ingest_directory(self, knowledge_dir: str | Path, *, reset: bool = True) -> int:
        docs = load_knowledge_documents(Path(knowledge_dir))
        return self.ingest(docs, reset=reset)

    def count(self) -> int:
        return self._collection.count()

    def query(self, query_text: str, *, n_results: int = 3) -> list[Citation]:
        if self.count() == 0:
            return []

        n = min(n_results, self.count())
        raw = self._collection.query(
            query_texts=[query_text],
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )
        citations: list[Citation] = []
        ids = (raw.get("ids") or [[]])[0]
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]

        for doc_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
            meta = metadata or {}
            typologies = [t for t in str(meta.get("typologies", "")).split(",") if t]
            # Prefer body text after title/keywords lines when present
            snippet = document or ""
            citations.append(
                Citation(
                    doc_id=doc_id,
                    title=str(meta.get("title") or doc_id),
                    source_path=str(meta.get("source_path") or ""),
                    snippet=snippet,
                    typologies=typologies,
                    distance=float(distance) if distance is not None else None,
                )
            )
        return citations
