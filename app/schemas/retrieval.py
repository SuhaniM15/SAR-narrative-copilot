"""Schemas for knowledge docs and retrieval citations."""

from typing import Optional

from pydantic import BaseModel, Field


class KnowledgeDocument(BaseModel):
    doc_id: str
    title: str
    keywords: str
    text: str
    source_path: str
    # Tags used to prefer typology-matched policy docs
    typologies: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    doc_id: str
    title: str
    source_path: str
    snippet: str
    typologies: list[str] = Field(default_factory=list)
    # Chroma returns distance (lower = closer). Exposed for explainability.
    distance: Optional[float] = None


class RetrievalResult(BaseModel):
    query: str
    citations: list[Citation] = Field(default_factory=list)
    # Concatenated policy context for the LLM prompt
    policy_context: str = ""
