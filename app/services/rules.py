"""Deterministic typology rule engine (structuring / layering).

Interview framing: rules produce explainable findings from transaction evidence.
The LLM narrates; it does not invent the suspicion patterns.
"""

from __future__ import annotations

from datetime import timedelta

from app.schemas.evidence import EvidenceTransaction, TypologyFinding

# US CTR threshold — "near threshold" cash deposits sit just below this.
_CTR_THRESHOLD = 10_000.0
_NEAR_THRESHOLD_MIN = 9_000.0

# Windows used by velocity / multi-location rules (days).
_STRUCT_LOCATION_WINDOW_DAYS = 7
_LAYER_RAPID_EXIT_DAYS = 5

_CASH_DEPOSIT_TYPES = {"cash_deposit", "deposit_cash", "cash"}
_OUTFLOW_TYPES = {"wire_out", "wire", "transfer_out", "ach_out"}


def _is_cash_deposit(txn: EvidenceTransaction) -> bool:
    return txn.txn_type.lower().replace(" ", "_") in _CASH_DEPOSIT_TYPES or (
        "cash" in txn.txn_type.lower() and "deposit" in txn.txn_type.lower()
    )


def _is_outflow(txn: EvidenceTransaction) -> bool:
    t = txn.txn_type.lower().replace(" ", "_")
    if t in _OUTFLOW_TYPES:
        return True
    return "wire" in t and "in" not in t


def _is_near_threshold_cash(txn: EvidenceTransaction) -> bool:
    return (
        _is_cash_deposit(txn)
        and _NEAR_THRESHOLD_MIN <= txn.amount < _CTR_THRESHOLD
    )


def _is_international_location(location: str) -> bool:
    """Heuristic: treat non-empty locations outside common US markers as international."""
    loc = (location or "").strip().lower()
    if not loc:
        return False
    us_markers = (
        ", us",
        " usa",
        "united states",
        ", al", ", ak", ", az", ", ar", ", ca", ", co", ", ct", ", de", ", fl",
        ", ga", ", hi", ", id", ", il", ", in", ", ia", ", ks", ", ky", ", la",
        ", me", ", md", ", ma", ", mi", ", mn", ", ms", ", mo", ", mt", ", ne",
        ", nv", ", nh", ", nj", ", nm", ", ny", ", nc", ", nd", ", oh", ", ok",
        ", or", ", pa", ", ri", ", sc", ", sd", ", tn", ", tx", ", ut", ", vt",
        ", va", ", wa", ", wv", ", wi", ", wy", ", dc",
    )
    # Explicit offshore / foreign cues
    foreign_cues = (
        "cayman", "bahamas", "panama", "switzerland", "dubai", "hong kong",
        "singapore", "offshore", "bvi", "jersey", "luxembourg", "cyprus",
    )
    if any(cue in loc for cue in foreign_cues):
        return True
    if loc.endswith(", us") or loc == "us" or loc.endswith(" usa"):
        return False
    # "Miami, FL" style → domestic
    if any(loc.endswith(m.strip()) or m.strip() in loc for m in (", fl", ", ny", ", ca", ", tx")):
        return False
    if any(marker.strip() in loc for marker in us_markers if len(marker.strip()) > 3):
        return False
    # If it has a US state abbreviation pattern "xx, yy" with 2-letter state, treat domestic
    parts = [p.strip() for p in loc.split(",")]
    if len(parts) >= 2 and len(parts[-1]) == 2 and parts[-1].isalpha():
        return False
    return True


def evaluate_typology_rules(
    transactions: list[EvidenceTransaction],
    *,
    typologies: list[str] | None = None,
) -> list[TypologyFinding]:
    """Run STRUCT/LAYER rules. Order is stable for tests and prompts."""
    _ = typologies  # reserved for future rule gating by case typology tags
    findings: list[TypologyFinding] = []
    txns = sorted(transactions, key=lambda t: t.occurred_at)

    near = [t for t in txns if _is_near_threshold_cash(t)]
    if len(near) >= 2:
        findings.append(
            TypologyFinding(
                rule_id="STRUCT-001",
                finding="Multiple cash deposits near reporting threshold",
                evidence_txn_refs=[t.txn_ref for t in near],
            )
        )

    cash = [t for t in txns if _is_cash_deposit(t)]
    if len(cash) >= 2:
        # Any pair of cash deposits at different locations within the window
        hit_refs: list[str] = []
        for i, a in enumerate(cash):
            for b in cash[i + 1 :]:
                if a.location.strip().lower() == b.location.strip().lower():
                    continue
                delta = abs((b.occurred_at - a.occurred_at).total_seconds())
                if delta <= timedelta(days=_STRUCT_LOCATION_WINDOW_DAYS).total_seconds():
                    hit_refs.extend([a.txn_ref, b.txn_ref])
        # Dedupe preserving order
        seen: set[str] = set()
        ordered = []
        for ref in hit_refs:
            if ref not in seen:
                seen.add(ref)
                ordered.append(ref)
        if len(ordered) >= 2:
            findings.append(
                TypologyFinding(
                    rule_id="STRUCT-002",
                    finding="Cash deposits distributed across locations within a short period",
                    evidence_txn_refs=ordered,
                )
            )

    outflows = [t for t in txns if _is_outflow(t)]
    if cash and outflows:
        rapid_refs: list[str] = []
        for out in outflows:
            prior = [
                c
                for c in cash
                if c.occurred_at <= out.occurred_at
                and (out.occurred_at - c.occurred_at)
                <= timedelta(days=_LAYER_RAPID_EXIT_DAYS)
            ]
            if prior:
                rapid_refs.extend([c.txn_ref for c in prior])
                rapid_refs.append(out.txn_ref)
        seen_r: set[str] = set()
        rapid_ordered = []
        for ref in rapid_refs:
            if ref not in seen_r:
                seen_r.add(ref)
                rapid_ordered.append(ref)
        if len(rapid_ordered) >= 2:
            findings.append(
                TypologyFinding(
                    rule_id="LAYER-001",
                    finding="Rapid movement of funds after deposits",
                    evidence_txn_refs=rapid_ordered,
                )
            )

    if near and outflows:
        intl_refs: list[str] = []
        for out in outflows:
            if not _is_international_location(out.location):
                continue
            prior_near = [c for c in near if c.occurred_at <= out.occurred_at]
            if prior_near:
                intl_refs.extend([c.txn_ref for c in prior_near])
                intl_refs.append(out.txn_ref)
        seen_i: set[str] = set()
        intl_ordered = []
        for ref in intl_refs:
            if ref not in seen_i:
                seen_i.add(ref)
                intl_ordered.append(ref)
        if len(intl_ordered) >= 2:
            findings.append(
                TypologyFinding(
                    rule_id="LAYER-002",
                    finding="Funds transferred internationally after suspicious deposit activity",
                    evidence_txn_refs=intl_ordered,
                )
            )

    return findings
