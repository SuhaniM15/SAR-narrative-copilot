"""Grounding checks — reject invented transaction references.

Interview point: LLMs hallucinate IDs. We treat txn refs as a closed allow-list
and fail closed when the draft cites something not in the evidence pack.
"""

from __future__ import annotations

import re

from app.schemas.drafting import StructuredNarrative

# Matches refs like TXN-1001, T1, ALT-style left alone; focused on TXN-* plus generic allow-list membership
_TXN_REF_PATTERN = re.compile(r"\bTXN-[A-Za-z0-9_-]+\b", re.IGNORECASE)


class GroundingError(ValueError):
    """Draft cited transaction evidence that is not in the allow-list."""


def extract_txn_refs_from_text(*parts: str) -> set[str]:
    found: set[str] = set()
    for part in parts:
        for match in _TXN_REF_PATTERN.findall(part or ""):
            found.add(match.upper() if match.upper().startswith("TXN-") else match)
    # Normalize to the casing used in allow-list later via case-insensitive compare
    return found


def validate_narrative_grounding(
    narrative: StructuredNarrative,
    allowed_txn_refs: list[str],
) -> list[str]:
    """Return warning notes; raise GroundingError on invented TXN-* citations."""
    allowed_map = {ref.upper(): ref for ref in allowed_txn_refs}
    allowed_upper = set(allowed_map.keys())
    notes: list[str] = []

    # Normalize model-declared refs
    cleaned_declared: list[str] = []
    invented_declared: list[str] = []
    for ref in narrative.evidence_txn_refs:
        key = ref.upper()
        if key in allowed_upper:
            cleaned_declared.append(allowed_map[key])
        else:
            invented_declared.append(ref)

    if invented_declared:
        raise GroundingError(
            f"Model declared evidence_txn_refs not in allow-list: {invented_declared}"
        )

    narrative.evidence_txn_refs = cleaned_declared

    # Scan narrative prose for TXN-* tokens
    prose_refs = extract_txn_refs_from_text(
        narrative.who,
        narrative.what,
        narrative.when,
        narrative.where,
        narrative.why,
        narrative.how,
        narrative.full_narrative,
    )
    invented_prose = sorted(r for r in prose_refs if r.upper() not in allowed_upper)
    if invented_prose:
        raise GroundingError(
            f"Narrative text cites transaction refs not in allow-list: {invented_prose}"
        )

    # If prose cites nothing but we have txns, soft note (not a failure)
    if allowed_txn_refs and not prose_refs and not cleaned_declared:
        notes.append("Draft did not cite any transaction refs; analyst should verify completeness.")

    # Prefer union of declared + prose for persistence
    cited = {allowed_map[r.upper()] for r in prose_refs if r.upper() in allowed_upper}
    cited.update(cleaned_declared)
    narrative.evidence_txn_refs = [ref for ref in allowed_txn_refs if ref in cited] or cleaned_declared

    return notes
