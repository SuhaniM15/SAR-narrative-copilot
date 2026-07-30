from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_roles
from app.models.audit import AuditEvent
from app.models.case import Case, NarrativeDraft
from app.models.user import User, UserRole
from app.schemas import (
    AuditEventOut,
    CaseCreate,
    CaseDecision,
    CaseListItem,
    CaseOut,
    DraftOut,
    DraftUpdate,
    MessageOut,
)
from app.services import cases as case_service
from app.services.audit import log_event

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreate,
    db: DbSession,
    current_user: User = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN)),
) -> Case:
    existing = db.scalars(
        select(Case).where(Case.external_alert_id == payload.external_alert_id)
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Alert ID already exists")
    return case_service.create_case(db, payload, current_user)


@router.get("", response_model=list[CaseListItem])
def list_cases(
    db: DbSession,
    _: User = Depends(require_roles(UserRole.ANALYST, UserRole.REVIEWER, UserRole.ADMIN)),
) -> list[Case]:
    return case_service.list_cases(db)


@router.get("/{case_id}", response_model=CaseOut)
def get_case(
    case_id: int,
    db: DbSession,
    _: User = Depends(require_roles(UserRole.ANALYST, UserRole.REVIEWER, UserRole.ADMIN)),
) -> Case:
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return case


@router.get("/{case_id}/drafts", response_model=list[DraftOut])
def list_drafts(
    case_id: int,
    db: DbSession,
    _: User = Depends(require_roles(UserRole.ANALYST, UserRole.REVIEWER, UserRole.ADMIN)),
) -> list[NarrativeDraft]:
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return case.drafts


@router.patch("/{case_id}/draft", response_model=DraftOut)
def update_latest_draft(
    case_id: int,
    payload: DraftUpdate,
    db: DbSession,
    current_user: User = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN)),
) -> NarrativeDraft:
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if not case.drafts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No draft exists yet")

    draft = case.drafts[-1]
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(draft, key, value)

    log_event(
        db,
        event_type="DRAFT_EDITED",
        summary=f"Draft v{draft.version} edited for case {case.external_alert_id}",
        actor=current_user,
        entity_id=case.id,
        detail={"draft_id": draft.id, "fields": list(updates.keys())},
    )
    db.commit()
    db.refresh(draft)
    return draft


@router.post("/{case_id}/submit", response_model=CaseOut)
def submit_case(
    case_id: int,
    db: DbSession,
    current_user: User = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN)),
) -> Case:
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    try:
        return case_service.submit_for_review(db, case, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{case_id}/approve", response_model=CaseOut)
def approve_case(
    case_id: int,
    payload: CaseDecision,
    db: DbSession,
    current_user: User = Depends(require_roles(UserRole.REVIEWER, UserRole.ADMIN)),
) -> Case:
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    try:
        return case_service.decide_case(db, case, current_user, approve=True, comment=payload.comment)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{case_id}/reject", response_model=CaseOut)
def reject_case(
    case_id: int,
    payload: CaseDecision,
    db: DbSession,
    current_user: User = Depends(require_roles(UserRole.REVIEWER, UserRole.ADMIN)),
) -> Case:
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    try:
        return case_service.decide_case(db, case, current_user, approve=False, comment=payload.comment)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{case_id}/audit", response_model=list[AuditEventOut])
def case_audit_trail(
    case_id: int,
    db: DbSession,
    _: User = Depends(require_roles(UserRole.ANALYST, UserRole.REVIEWER, UserRole.ADMIN)),
) -> list[AuditEvent]:
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.entity_type == "case", AuditEvent.entity_id == case_id)
        .order_by(AuditEvent.created_at.asc())
    )
    return list(db.scalars(stmt).all())


@router.post("/{case_id}/generate-draft", response_model=MessageOut)
def generate_draft_placeholder(
    case_id: int,
    db: DbSession,
    _: User = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN)),
) -> MessageOut:
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return MessageOut(
        detail="Draft generation lands in Week 2 (RAG + Groq adapter).",
        data={"case_id": case.id, "status": case.status},
    )
