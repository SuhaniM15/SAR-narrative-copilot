import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.user import User


def log_event(
    db: Session,
    *,
    event_type: str,
    summary: str,
    actor: Optional[User] = None,
    entity_type: str = "case",
    entity_id: Optional[int] = None,
    detail: Optional[dict[str, Any]] = None,
) -> AuditEvent:
    """Append an immutable audit event. Callers must commit the session."""
    event = AuditEvent(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor.id if actor else None,
        actor_role=actor.role if actor else None,
        summary=summary,
        detail_json=json.dumps(detail or {}),
    )
    db.add(event)
    db.flush()
    return event
