"""Offline AI pipeline demo: real RAG + FakeLLM (no Groq key needed)."""

import json

from sqlalchemy import select

from app.adapters.llm import FakeLLMAdapter
from app.database import SessionLocal
from app.models.case import Case
from app.models.user import User
from app.services.cases import get_case
from app.services.generation import generate_and_persist_draft


def main() -> None:
    fake = json.dumps(
        {
            "who": "Jordan Hale (CUST-88421), retail consultant.",
            "what": (
                "Multiple near-threshold cash deposits (TXN-1001, TXN-1002, TXN-1003) "
                "followed by offshore wire TXN-1004."
            ),
            "when": "1–5 July 2026.",
            "where": "Miami and Fort Lauderdale, FL branches; wire to Cayman Islands.",
            "why": "Activity inconsistent with expected payroll/domestic spending under $3,000/week.",
            "how": "Structuring via split cash deposits then rapid layering through offshore wire.",
            "full_narrative": (
                "The subject, Jordan Hale, conducted cash deposits TXN-1001, TXN-1002, and TXN-1003 "
                "just below $10,000 across Florida branches, then transmitted TXN-1004 ($28,000) "
                "to Offshore Holdings Ltd in the Cayman Islands."
            ),
            "evidence_txn_refs": ["TXN-1001", "TXN-1002", "TXN-1003", "TXN-1004"],
        }
    )

    db = SessionLocal()
    try:
        analyst = db.scalars(select(User).where(User.email == "analyst@example.com")).one()
        case_row = db.scalars(select(Case).where(Case.external_alert_id == "ALT-2026-0001")).one()
        case = get_case(db, case_row.id)
        assert case is not None

        print("=== OFFLINE AI DEMO (FakeLLM + real Chroma RAG) ===\n")
        print(f"Case: {case.external_alert_id} status={case.status}")
        draft = generate_and_persist_draft(db, case, analyst, llm=FakeLLMAdapter(fake))
        print(f"Saved draft v{draft.version} model={draft.model_name}")
        print(f"Case status now: {case.status}")
        print("\n--- 5 Ws ---")
        print("WHO:", draft.who)
        print("WHAT:", draft.what)
        print("WHEN:", draft.when)
        print("WHERE:", draft.where)
        print("WHY:", draft.why)
        print("HOW:", draft.how)
        print("\nCitations (truncated):", draft.retrieval_citations_json[:280], "...")
        print("Txn refs:", draft.evidence_txn_refs_json)
    finally:
        db.close()


if __name__ == "__main__":
    main()
