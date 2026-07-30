from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_roles
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas import Token, UserCreate, UserOut
from app.services.audit import log_event

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(db: DbSession, form_data: OAuth2PasswordRequestForm = Depends()) -> Token:
    # OAuth2 form uses "username" field; we treat it as email.
    user = db.scalars(select(User).where(User.email == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")

    token = create_access_token(subject=user.email, extra_claims={"role": user.role, "uid": user.id})
    log_event(
        db,
        event_type="USER_LOGIN",
        summary=f"User {user.email} logged in",
        actor=user,
        entity_type="user",
        entity_id=user.id,
    )
    db.commit()
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def me(current_user: CurrentUser) -> User:
    return current_user


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: DbSession,
    _: User = Depends(require_roles(UserRole.ADMIN)),
) -> User:
    existing = db.scalars(select(User).where(User.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    if payload.role not in {r.value for r in UserRole}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.flush()
    log_event(
        db,
        event_type="USER_CREATED",
        summary=f"User {user.email} created with role {user.role}",
        actor=_,
        entity_type="user",
        entity_id=user.id,
        detail={"role": user.role},
    )
    db.commit()
    db.refresh(user)
    return user
