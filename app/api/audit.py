from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import require_roles
from app.models.audit import AuditEvent
from app.models.user import User, UserRole
from app.schemas import AuditEventOut
from app.api.deps import DbSession

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events", response_model=list[AuditEventOut])
def list_recent_events(
    db: DbSession,
    _: User = Depends(require_roles(UserRole.REVIEWER, UserRole.ADMIN)),
    limit: int = 50,
) -> list[AuditEvent]:
    stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(min(limit, 200))
    return list(db.scalars(stmt).all())
