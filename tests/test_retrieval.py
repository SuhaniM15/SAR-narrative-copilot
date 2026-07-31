"""RAG loader + Chroma retrieval tests (no Groq, no network model required)."""

from datetime import datetime, timezone
from pathlib import Path

from app.adapters.chroma_retriever import ChromaKnowledgeStore, DeterministicHashEmbedding
from app.adapters.knowledge_loader import load_knowledge_documents, parse_knowledge_markdown
from app.config import BASE_DIR
from app.models.case import Case, CaseStatus, Transaction, Typology
from app.services.evidence import build_evidence_pack
from app.services.retrieval import retrieve_policy_context


def test_parse_knowledge_markdown():
    path = BASE_DIR / "data" / "knowledge" / "structuring.md"
    doc = parse_knowledge_markdown(path)
    assert doc.doc_id == "structuring"
    assert "Structuring" in doc.title
    assert "threshold" in doc.text.lower()
    assert doc.typologies == ["structuring"]


def test_load_all_knowledge_docs():
    docs = load_knowledge_documents(BASE_DIR / "data" / "knowledge")
    ids = {d.doc_id for d in docs}
    assert {"structuring", "layering", "fincen_5ws"} <= ids


def test_chroma_retrieve_for_structuring_layering_case(tmp_path: Path):
    store = ChromaKnowledgeStore(
        persist_dir=tmp_path / "chroma",
        collection_name="test_sar_knowledge",
        embedding_function=DeterministicHashEmbedding(),
    )
    count = store.ingest_directory(BASE_DIR / "data" / "knowledge", reset=True)
    assert count == 3

    case = Case(
        id=1,
        external_alert_id="ALT-RAG-1",
        title="Structuring then offshore wire",
        status=CaseStatus.OPEN.value,
        typology=Typology.STRUCTURING_LAYERING.value,
        jurisdiction="FinCEN",
        alert_reason="Near-threshold cash deposits followed by rapid offshore wire",
        risk_score=0.9,
        customer_id="CUST-1",
        customer_name="Jordan Hale",
        customer_occupation="Retail consultant",
        customer_expected_activity="Payroll under $3,000/week",
        customer_country="US",
        transactions=[
            Transaction(
                id=1,
                case_id=1,
                txn_ref="TXN-1001",
                amount=9800.0,
                currency="USD",
                txn_type="cash_deposit",
                counterparty="Cash",
                location="Miami, FL",
                channel="branch",
                occurred_at=datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc),
            ),
            Transaction(
                id=2,
                case_id=1,
                txn_ref="TXN-1004",
                amount=28000.0,
                currency="USD",
                txn_type="wire_out",
                counterparty="Offshore Holdings Ltd",
                location="Cayman Islands",
                channel="wire",
                occurred_at=datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc),
            ),
        ],
    )
    pack = build_evidence_pack(case)
    result = retrieve_policy_context(pack, store=store, top_k=3)

    assert result.query == pack.rag_query
    assert len(result.citations) == 3
    cite_ids = {c.doc_id for c in result.citations}
    # Typology-aware ranking should keep structuring/layering and/or FinCEN guidance
    assert cite_ids & {"structuring", "layering", "fincen_5ws"}
    assert result.policy_context
    assert all(c.title and c.snippet for c in result.citations)
