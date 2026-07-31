"""Rebuild the Chroma knowledge index from data/knowledge/*.md

Usage:
  python -m scripts.ingest_knowledge
"""

from app.services.retrieval import rebuild_knowledge_index, reset_knowledge_store_cache


def main() -> None:
    reset_knowledge_store_cache()
    count = rebuild_knowledge_index()
    print(f"Ingested {count} knowledge documents into Chroma.")


if __name__ == "__main__":
    main()
