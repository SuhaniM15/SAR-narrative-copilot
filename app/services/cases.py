from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.case import Case, CaseStatus, Transaction
from app.models.user import User
from app.schemas import CaseCreate
from app.services.audit import log_event


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
    if case.status not in {CaseStatus.DRAFTED.value, CaseStatus.OPEN.value}:
        raise ValueError(f"Cannot submit case in status '{case.status}' for review")
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
    if case.status not in {CaseStatus.UNDER_REVIEW.value, CaseStatus.DRAFTED.value}:
        raise ValueError(f"Cannot decide case in status '{case.status}'")

    case.status = CaseStatus.APPROVED.value if approve else CaseStatus.REJECTED.value
    event_type = "CASE_APPROVED" if approve else "CASE_REJECTED"
    log_event(
        db,
        event_type=event_type,
        summary=f"Case {case.external_alert_id} {case.status}",
        actor=actor,
        entity_id=case.id,
        detail={"status": case.status, "comment": comment},
    )
    db.commit()
    db.refresh(case)
    return case
