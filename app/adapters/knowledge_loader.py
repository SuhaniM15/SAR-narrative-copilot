"""Load curated policy/typology markdown into KnowledgeDocument objects.

We intentionally avoid LangChain document loaders — small custom parser,
easy to explain in interviews, zero magic.
"""

from pathlib import Path

from app.schemas.retrieval import KnowledgeDocument

# Filename → typology tags this doc is primarily about.
# "general" docs (FinCEN 5 Ws) apply to every case.
_FILE_TYPOLOGIES: dict[str, list[str]] = {
    "structuring.md": ["structuring"],
    "layering.md": ["layering"],
    "fincen_5ws.md": ["general", "fincen"],
}


def parse_knowledge_markdown(path: Path) -> KnowledgeDocument:
    """Parse our simple title/keywords/text knowledge format."""
    raw = path.read_text(encoding="utf-8")
    title = ""
    keywords = ""
    text_lines: list[str] = []
    in_text = False

    for line in raw.splitlines():
        if in_text:
            # YAML block scalar style in our files: strip one indent level if present
            text_lines.append(line[2:] if line.startswith("  ") else line)
            continue
        if line.startswith("title:"):
            title = line.split(":", 1)[1].strip()
        elif line.startswith("keywords:"):
            keywords = line.split(":", 1)[1].strip()
        elif line.startswith("text:"):
            in_text = True

    text = "\n".join(text_lines).strip()
    if not title or not text:
        raise ValueError(f"Knowledge file missing title/text: {path}")

    typologies = list(_FILE_TYPOLOGIES.get(path.name, ["general"]))
    return KnowledgeDocument(
        doc_id=path.stem,
        title=title,
        keywords=keywords,
        text=text,
        source_path=str(path.as_posix()),
        typologies=typologies,
    )


def load_knowledge_documents(knowledge_dir: Path) -> list[KnowledgeDocument]:
    if not knowledge_dir.exists():
        raise FileNotFoundError(f"Knowledge directory not found: {knowledge_dir}")
    docs: list[KnowledgeDocument] = []
    for path in sorted(knowledge_dir.glob("*.md")):
        docs.append(parse_knowledge_markdown(path))
    return docs
