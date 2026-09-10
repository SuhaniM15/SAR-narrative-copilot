from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.case import Case, CaseStatus, NarrativeDraft, Transaction
from app.models.user import User
from app.schemas import CaseCreate, DraftUpdate
from app.services.audit import log_event

_EDITABLE_STATUSES = {
    CaseStatus.OPEN.value,
    CaseStatus.DRAFTED.value,
    CaseStatus.REJECTED.value,
}

_SUBMITTABLE_STATUSES = {
    CaseStatus.OPEN.value,
    CaseStatus.DRAFTED.value,
    CaseStatus.REJECTED.value,
}

_DECISION_STATUSES = {
    CaseStatus.UNDER_REVIEW.value,
    CaseStatus.DRAFTED.value,
}


def create_case(db: Session, payload: CaseCreate, actor: User) -> Case:
    case = Case(
        external_alert_id=payload.external_alert_id,
        title=payload.title,
        status=CaseStatus.OPEN.value,
        typology=payload.typology,
        jurisdiction=payload.jurisdiction,
        alert_reason=payload.alert_reason,
        risk_score=payload.risk_score,
        customer_id=payload.customer_id,
        customer_name=payload.customer_name,
        customer_occupation=payload.customer_occupation,
        customer_expected_activity=payload.customer_expected_activity,
        customer_country=payload.customer_country,
        created_by_id=actor.id,
        assigned_to_id=actor.id,
    )
    for txn in payload.transactions:
        case.transactions.append(Transaction(**txn.model_dump()))

    db.add(case)
    db.flush()

    log_event(
        db,
        event_type="CASE_CREATED",
        summary=f"Case {case.external_alert_id} created",
        actor=actor,
        entity_id=case.id,
        detail={
            "external_alert_id": case.external_alert_id,
            "typology": case.typology,
            "transaction_count": len(case.transactions),
        },
    )
    db.commit()
    db.refresh(case)
    return get_case(db, case.id)


def list_cases(db: Session) -> list[Case]:
    stmt = select(Case).order_by(Case.created_at.desc())
    return list(db.scalars(stmt).all())


def get_case(db: Session, case_id: int) -> Case | None:
    stmt = (
        select(Case)
        .where(Case.id == case_id)
        .options(selectinload(Case.transactions), selectinload(Case.drafts))
    )
    return db.scalars(stmt).first()


def submit_for_review(db: Session, case: Case, actor: User) -> Case:
    if case.status not in _SUBMITTABLE_STATUSES:
        raise ValueError(f"Cannot submit case in status '{case.status}' for review")
    if not case.drafts:
        raise ValueError("Cannot submit for review without a narrative draft")
    case.status = CaseStatus.UNDER_REVIEW.value
    log_event(
        db,
        event_type="CASE_SUBMITTED_FOR_REVIEW",
        summary=f"Case {case.external_alert_id} submitted for review",
        actor=actor,
        entity_id=case.id,
        detail={"status": case.status},
    )
    db.commit()
    db.refresh(case)
    return case


def decide_case(db: Session, case: Case, actor: User, *, approve: bool, comment: str) -> Case:
    if case.status == CaseStatus.APPROVED.value:
        raise ValueError("Case is already approved; drafts cannot be overwritten")
    if case.status not in _DECISION_STATUSES:
        raise ValueError(f"Cannot decide case in status '{case.status}'")

    if approve:
        case.status = CaseStatus.APPROVED.value
        event_type = "CASE_APPROVED"
        summary = f"Case {case.external_alert_id} approved"
    else:
        # Rejection returns the case to drafted so analyst can revise / resubmit.
        case.status = CaseStatus.DRAFTED.value
        event_type = "CASE_REJECTED"
        summary = (
            f"Case {case.external_alert_id} rejected — returned to drafted for revision"
        )

    log_event(
        db,
        event_type=event_type,
        summary=summary,
        actor=actor,
        entity_id=case.id,
        detail={
            "status": case.status,
            "comment": comment,
            "decision": "approved" if approve else "rejected",
        },
    )
    db.commit()
    db.refresh(case)
    return case


def edit_latest_draft(
    db: Session,
    case: Case,
    actor: User,
    payload: DraftUpdate,
) -> NarrativeDraft:
    """Analyst edits create a new draft version (history preserved).

    Approved / under_review cases cannot be casually overwritten.
    """
    if case.status == CaseStatus.APPROVED.value:
        raise ValueError("Cannot edit draft on an approved case")
    if case.status == CaseStatus.UNDER_REVIEW.value:
        raise ValueError("Cannot edit draft while case is under review")
    if case.status not in _EDITABLE_STATUSES:
        raise ValueError(f"Cannot edit draft while case status is '{case.status}'")
    if not case.drafts:
        raise ValueError("No draft exists yet")

    latest = case.drafts[-1]
    updates = payload.model_dump(exclude_unset=True)
    next_version = latest.version + 1

    new_draft = NarrativeDraft(
        case_id=case.id,
        version=next_version,
        who=updates.get("who", latest.who),
        what=updates.get("what", latest.what),
        when=updates.get("when", latest.when),
        where=updates.get("where", latest.where),
        why=updates.get("why", latest.why),
        how=updates.get("how", latest.how),
        full_narrative=updates.get("full_narrative", latest.full_narrative),
        model_name=latest.model_name,
        retrieval_citations_json=latest.retrieval_citations_json,
        evidence_txn_refs_json=latest.evidence_txn_refs_json,
        created_by_id=actor.id,
    )
    case.drafts.append(new_draft)
    if case.status == CaseStatus.REJECTED.value:
        case.status = CaseStatus.DRAFTED.value

    db.add(new_draft)
    db.flush()

    log_event(
        db,
        event_type="DRAFT_EDITED",
        summary=(
            f"Draft v{new_draft.version} created from v{latest.version} "
            f"for case {case.external_alert_id}"
        ),
        actor=actor,
        entity_id=case.id,
        detail={
            "draft_id": new_draft.id,
            "version": new_draft.version,
            "previous_version": latest.version,
            "fields": list(updates.keys()),
            "status": case.status,
        },
    )
    db.commit()
    db.refresh(new_draft)
    return new_draft
