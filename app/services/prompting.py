"""Prompt construction for FinCEN-style structured SAR drafts."""

from app.schemas.drafting import LLMMessage
from app.schemas.evidence import EvidencePack
from app.schemas.retrieval import RetrievalResult

SYSTEM_PROMPT = """You are a bank compliance copilot helping an analyst draft a FinCEN-style
Suspicious Activity Report narrative. You write factual, chronological, regulator-useful prose.

Hard rules:
1. Use ONLY facts from the CASE EVIDENCE block. Do not invent customers, amounts, dates, locations, or transaction IDs.
2. You may use POLICY CONTEXT for narrative structure and typology language — not as new case facts.
3. Every transaction ID you mention MUST appear in allowed_txn_refs.
4. Respond with a single JSON object (no markdown) with keys:
   who, what, when, where, why, how, full_narrative, evidence_txn_refs
5. evidence_txn_refs must be an array of txn_ref strings taken from allowed_txn_refs only.
6. full_narrative should weave the 5 Ws + How into a coherent SAR narrative paragraph set.
7. If evidence is thin, say what is known and what is not evidenced — do not speculate.
"""


def build_draft_messages(pack: EvidencePack, retrieval: RetrievalResult) -> list[LLMMessage]:
    allowed = ", ".join(pack.allowed_txn_refs) or "(none)"
    user = f"""CASE EVIDENCE (sole factual source):
{pack.llm_context}

allowed_txn_refs: [{allowed}]
typologies: {", ".join(pack.typologies) or pack.case.typology}
jurisdiction: {pack.case.jurisdiction}

POLICY CONTEXT (retrieval citations — guidance only):
{retrieval.policy_context or "(no policy snippets retrieved)"}

Return JSON now."""

    return [
        LLMMessage(role="system", content=SYSTEM_PROMPT),
        LLMMessage(role="user", content=user),
    ]
