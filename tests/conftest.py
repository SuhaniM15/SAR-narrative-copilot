import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app.core.security import hash_password
from app.database import Base, get_db
from app.main import create_app
from app.models.user import User, UserRole


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    analyst = User(
        email="analyst@example.com",
        full_name="Test Analyst",
        hashed_password=hash_password("AnalystPass123!"),
        role=UserRole.ANALYST.value,
    )
    reviewer = User(
        email="reviewer@example.com",
        full_name="Test Reviewer",
        hashed_password=hash_password("ReviewerPass123!"),
        role=UserRole.REVIEWER.value,
    )
    db_session.add_all([analyst, reviewer])
    db_session.commit()

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def analyst_token(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "analyst@example.com", "password": "AnalystPass123!"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture()
def reviewer_token(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "reviewer@example.com", "password": "ReviewerPass123!"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]
