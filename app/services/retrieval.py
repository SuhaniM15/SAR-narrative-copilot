"""Retrieval service — EvidencePack → policy citations.

Pipeline position: Evidence Pack → (this) → Groq prompt builder.
"""

from pathlib import Path

from app.adapters.chroma_retriever import ChromaKnowledgeStore
from app.config import get_settings
from app.schemas.evidence import EvidencePack
from app.schemas.retrieval import Citation, RetrievalResult

_store: ChromaKnowledgeStore | None = None


def get_knowledge_store() -> ChromaKnowledgeStore:
    """Process-level store. Tests can call reset_knowledge_store_cache()."""
    global _store
    if _store is None:
        settings = get_settings()
        _store = ChromaKnowledgeStore(
            persist_dir=settings.chroma_dir,
            collection_name=settings.chroma_collection,
        )
    return _store


def reset_knowledge_store_cache() -> None:
    global _store
    _store = None


def ensure_knowledge_ingested(store: ChromaKnowledgeStore | None = None) -> int:
    """Idempotent bootstrap: ingest curated docs if the collection is empty."""
    settings = get_settings()
    store = store or get_knowledge_store()
    if store.count() > 0:
        return store.count()
    return store.ingest_directory(settings.knowledge_dir, reset=True)


def retrieve_policy_context(
    pack: EvidencePack,
    *,
    store: ChromaKnowledgeStore | None = None,
    top_k: int | None = None,
) -> RetrievalResult:
    """Retrieve typology/policy snippets grounded for this evidence pack."""
    settings = get_settings()
    store = store or get_knowledge_store()
    ensure_knowledge_ingested(store)

    k = top_k or settings.rag_top_k
    # Over-fetch then re-rank so typology matches + general FinCEN guidance survive
    candidates = store.query(pack.rag_query, n_results=max(k * 2, k))
    ranked = _rank_citations(candidates, pack.typologies)
    selected = ranked[:k]

    policy_blocks = []
    for cite in selected:
        policy_blocks.append(f"[{cite.doc_id}] {cite.title}\n{cite.snippet}")

    return RetrievalResult(
        query=pack.rag_query,
        citations=selected,
        policy_context="\n\n".join(policy_blocks),
    )


def _rank_citations(citations: list[Citation], typologies: list[str]) -> list[Citation]:
    """Prefer docs tagged with case typologies or 'general'; break ties by distance."""
    typology_set = set(typologies)

    def sort_key(cite: Citation) -> tuple:
        tags = set(cite.typologies)
        typology_hit = 1 if tags & typology_set else 0
        general_hit = 1 if "general" in tags or "fincen" in tags else 0
        distance = cite.distance if cite.distance is not None else 999.0
        # Higher hit score first, then lower distance
        return (-(typology_hit * 2 + general_hit), distance)

    return sorted(citations, key=sort_key)


def rebuild_knowledge_index(
    *,
    knowledge_dir: str | Path | None = None,
    store: ChromaKnowledgeStore | None = None,
) -> int:
    settings = get_settings()
    store = store or get_knowledge_store()
    path = Path(knowledge_dir or settings.knowledge_dir)
    return store.ingest_directory(path, reset=True)
