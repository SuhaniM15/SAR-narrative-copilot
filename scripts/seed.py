"""Seed demo users and a structuring/layering alert case."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import hash_password
from app.database import SessionLocal, init_db
from app.models.case import Case, CaseStatus, Transaction, Typology
from app.models.user import User, UserRole
from app.services.audit import log_event


USERS = [
    {
        "email": "admin@example.com",
        "full_name": "System Admin",
        "password": "AdminPass123!",
        "role": UserRole.ADMIN.value,
    },
    {
        "email": "analyst@example.com",
        "full_name": "Asha Analyst",
        "password": "AnalystPass123!",
        "role": UserRole.ANALYST.value,
    },
    {
        "email": "reviewer@example.com",
        "full_name": "Ravi Reviewer",
        "password": "ReviewerPass123!",
        "role": UserRole.REVIEWER.value,
    },
]


def seed_users(db) -> dict[str, User]:
    created: dict[str, User] = {}
    for item in USERS:
        user = db.scalars(select(User).where(User.email == item["email"])).first()
        if not user:
            user = User(
                email=item["email"],
                full_name=item["full_name"],
                hashed_password=hash_password(item["password"]),
                role=item["role"],
            )
            db.add(user)
            db.flush()
            log_event(
                db,
                event_type="USER_CREATED",
                summary=f"Seeded user {user.email}",
                actor=user,
                entity_type="user",
                entity_id=user.id,
                detail={"role": user.role, "seed": True},
            )
        created[item["role"]] = user
    db.commit()
    return created


def seed_sample_case(db, analyst: User) -> Case:
    alert_id = "ALT-2026-0001"
    existing = db.scalars(select(Case).where(Case.external_alert_id == alert_id)).first()
    if existing:
        return existing

    base = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    case = Case(
        external_alert_id=alert_id,
        title="Possible structuring and rapid offshore layering",
        status=CaseStatus.OPEN.value,
        typology=Typology.STRUCTURING_LAYERING.value,
        jurisdiction="FinCEN",
        alert_reason=(
            "Multiple cash deposits just below $10,000 across branches within 5 days, "
            "followed by an immediate wire to a high-risk offshore jurisdiction."
        ),
        risk_score=0.91,
        customer_id="CUST-88421",
        customer_name="Jordan Hale",
        customer_occupation="Retail consultant",
        customer_expected_activity="Payroll deposits and domestic spending under $3,000/week",
        customer_country="US",
        created_by_id=analyst.id,
        assigned_to_id=analyst.id,
        transactions=[
            Transaction(
                txn_ref="TXN-1001",
                amount=9800.0,
                currency="USD",
                txn_type="cash_deposit",
                counterparty="Cash - Branch 12",
                location="Miami, FL",
                channel="branch",
                occurred_at=base,
                narrative_note="Just below CTR threshold",
            ),
            Transaction(
                txn_ref="TXN-1002",
                amount=9500.0,
                currency="USD",
                txn_type="cash_deposit",
                counterparty="Cash - Branch 04",
                location="Fort Lauderdale, FL",
                channel="branch",
                occurred_at=base + timedelta(days=1),
                narrative_note="Second near-threshold deposit",
            ),
            Transaction(
                txn_ref="TXN-1003",
                amount=9700.0,
                currency="USD",
                txn_type="cash_deposit",
                counterparty="Cash - Branch 19",
                location="Miami, FL",
                channel="branch",
                occurred_at=base + timedelta(days=3),
                narrative_note="Third near-threshold deposit",
            ),
            Transaction(
                txn_ref="TXN-1004",
                amount=28000.0,
                currency="USD",
                txn_type="wire_out",
                counterparty="Offshore Holdings Ltd",
                location="Cayman Islands",
                channel="wire",
                occurred_at=base + timedelta(days=4, hours=2),
                narrative_note="Rapid aggregation then offshore exit",
            ),
        ],
    )
    db.add(case)
    db.flush()
    log_event(
        db,
        event_type="CASE_CREATED",
        summary=f"Seeded case {case.external_alert_id}",
        actor=analyst,
        entity_id=case.id,
        detail={"seed": True, "transaction_count": len(case.transactions)},
    )
    db.commit()
    db.refresh(case)
    return case


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        users = seed_users(db)
        case = seed_sample_case(db, users[UserRole.ANALYST.value])
        print("Seed complete.")
        print("Users:")
        for u in USERS:
            print(f"  {u['email']} / {u['password']}  ({u['role']})")
        print(f"Sample case id={case.id} alert={case.external_alert_id} status={case.status}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
