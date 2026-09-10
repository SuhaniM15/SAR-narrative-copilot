"""PII masking checkpoint — mask identifiers in LLM-bound context only.

Database / API responses keep real customer values. Masking applies to the
EvidencePack copy sent toward the external LLM. Not a legal-compliance claim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.schemas.evidence import EvidencePack, TypologyFinding

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


@dataclass
class PiiMaskResult:
    """Masked pack plus reverse map (placeholder → original) for debugging/tests."""

    pack: EvidencePack
    mapping: dict[str, str] = field(default_factory=dict)


def mask_evidence_pack_for_llm(pack: EvidencePack) -> PiiMaskResult:
    """Return a deep-copied pack with direct identifiers replaced by placeholders."""
    mapping: dict[str, str] = {}
    masked = pack.model_copy(deep=True)

    customer_token = "<CUSTOMER_001>"
    account_token = "<ACCOUNT_001>"

    real_name = (masked.customer.name or "").strip()
    real_id = (masked.customer.customer_id or "").strip()

    if real_name:
        mapping[customer_token] = real_name
        masked.customer.name = customer_token
    if real_id:
        mapping[account_token] = real_id
        masked.customer.customer_id = account_token

    # Mask emails found in free text; keep stable placeholders per distinct email.
    email_index = 1

    def _mask_emails(text: str) -> str:
        nonlocal email_index

        def repl(match: re.Match[str]) -> str:
            nonlocal email_index
            email = match.group(0)
            # Reuse placeholder if same email already mapped
            for token, original in mapping.items():
                if original == email and token.startswith("<EMAIL_"):
                    return token
            token = f"<EMAIL_{email_index:03d}>"
            email_index += 1
            mapping[token] = email
            return token

        return _EMAIL_RE.sub(repl, text or "")

    def _mask_known_identifiers(text: str) -> str:
        out = text or ""
        # Longer strings first to avoid partial clobbering
        if real_name:
            out = re.sub(re.escape(real_name), customer_token, out, flags=re.IGNORECASE)
        if real_id:
            out = re.sub(re.escape(real_id), account_token, out, flags=re.IGNORECASE)
        return _mask_emails(out)

    masked.case.title = _mask_known_identifiers(masked.case.title)
    masked.case.alert_reason = _mask_known_identifiers(masked.case.alert_reason)
    masked.customer.occupation = _mask_known_identifiers(masked.customer.occupation)
    masked.customer.expected_activity = _mask_known_identifiers(
        masked.customer.expected_activity
    )

    for txn in masked.transactions:
        txn.counterparty = _mask_known_identifiers(txn.counterparty)
        txn.narrative_note = _mask_known_identifiers(txn.narrative_note)
        # Do not mask txn_ref — required for grounding allow-list.

    masked.findings = [
        TypologyFinding(
            rule_id=f.rule_id,
            finding=_mask_known_identifiers(f.finding),
            evidence_txn_refs=list(f.evidence_txn_refs),
        )
        for f in masked.findings
    ]

    masked.llm_context = _mask_known_identifiers(masked.llm_context)
    masked.rag_query = _mask_known_identifiers(masked.rag_query)

    return PiiMaskResult(pack=masked, mapping=mapping)
