"""Build an EvidencePack from a loaded Case (+ transactions).

Why a separate service?
- Keeps prompt/RAG code free of SQLAlchemy details
- Makes grounding rules explicit (allowed_txn_refs)
- Lets us unit-test the brief without calling an LLM
"""

from app.models.case import Case
from app.schemas.evidence import (
    EvidenceCaseMeta,
    EvidenceCustomer,
    EvidencePack,
    EvidenceTransaction,
)

# Explicit map beats blind string-splitting (avoids breaking future typology names).
_TYPOLOGY_TO_TAGS: dict[str, list[str]] = {
    "structuring": ["structuring"],
    "layering": ["layering"],
    "structuring_layering": ["structuring", "layering"],
}


def normalize_typologies(typology: str) -> list[str]:
    """DB stores one label; pack exposes a list for multi-doc RAG."""
    tags = _TYPOLOGY_TO_TAGS.get(typology)
    if tags:
        return list(tags)
    # Unknown future value: keep as a single tag so nothing is silently dropped
    return [typology] if typology else []


def build_evidence_pack(case: Case) -> EvidencePack:
    """Convert a Case ORM object into the canonical LLM/RAG evidence brief."""
    transactions = [
        EvidenceTransaction(
            txn_ref=txn.txn_ref,
            amount=txn.amount,
            currency=txn.currency,
            txn_type=txn.txn_type,
            counterparty=txn.counterparty,
            location=txn.location,
            channel=txn.channel,
            occurred_at=txn.occurred_at,
            narrative_note=txn.narrative_note or "",
        )
        for txn in case.transactions
    ]
    allowed_txn_refs = [txn.txn_ref for txn in transactions]
    typologies = normalize_typologies(case.typology)

    return EvidencePack(
        case=EvidenceCaseMeta(
            case_id=case.id,
            external_alert_id=case.external_alert_id,
            title=case.title,
            status=case.status,
            typology=case.typology,
            jurisdiction=case.jurisdiction,
            alert_reason=case.alert_reason,
            risk_score=case.risk_score,
        ),
        customer=EvidenceCustomer(
            customer_id=case.customer_id,
            name=case.customer_name,
            occupation=case.customer_occupation,
            expected_activity=case.customer_expected_activity,
            country=case.customer_country,
        ),
        transactions=transactions,
        typologies=typologies,
        allowed_txn_refs=allowed_txn_refs,
        rag_query=_build_rag_query(case, typologies, transactions),
        llm_context=_build_llm_context(case, typologies, transactions),
    )


def _build_rag_query(
    case: Case,
    typologies: list[str],
    transactions: list[EvidenceTransaction],
) -> str:
    """Compact query for vector search — typology + suspicion theme + txn patterns."""
    txn_types = sorted({txn.txn_type for txn in transactions})
    typology_text = ", ".join(typologies) if typologies else case.typology
    channels = sorted({txn.channel for txn in transactions if txn.channel})
    return (
        f"FinCEN SAR narrative guidance for typologies: {typology_text}. "
        f"Alert theme: {case.alert_reason}. "
        f"Activity patterns: {', '.join(txn_types) or 'unknown'}; "
        f"channels: {', '.join(channels) or 'unknown'}."
    )


def _build_llm_context(
    case: Case,
    typologies: list[str],
    transactions: list[EvidenceTransaction],
) -> str:
    """Full factual brief. Downstream prompts must treat this as the sole case evidence."""
    txn_lines = []
    for txn in transactions:
        when = txn.occurred_at.isoformat()
        txn_lines.append(
            f"- {txn.txn_ref}: {txn.txn_type} {txn.amount} {txn.currency} "
            f"via {txn.channel} to/from {txn.counterparty} at {txn.location} on {when}"
            + (f" ({txn.narrative_note})" if txn.narrative_note else "")
        )
    txn_block = "\n".join(txn_lines) if txn_lines else "- (no transactions)"
    typology_text = ", ".join(typologies) if typologies else case.typology

    return (
        f"Alert {case.external_alert_id} | jurisdiction={case.jurisdiction} | "
        f"typologies=[{typology_text}] | risk_score={case.risk_score}.\n"
        f"Title: {case.title}\n"
        f"Alert reason: {case.alert_reason}\n"
        f"Customer: {case.customer_name} ({case.customer_id}), "
        f"occupation={case.customer_occupation}, country={case.customer_country}.\n"
        f"Expected activity: {case.customer_expected_activity}\n"
        f"Transactions:\n{txn_block}"
    )
