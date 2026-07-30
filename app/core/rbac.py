"""Simplify RBAC checks used by API dependencies."""

from fastapi import HTTPException, status

from app.models.user import User, UserRole


def assert_role(user: User, *allowed: UserRole) -> None:
    allowed_values = {role.value for role in allowed}
    if user.role not in allowed_values:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{user.role}' is not permitted for this action",
        )
