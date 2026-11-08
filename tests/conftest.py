"""
Global Pytest configuration and fixtures.
Provides isolated in-memory test database and client fixtures.
"""
import os
os.environ.setdefault("SMTP_FROM_EMAIL", "sonyvengala04@gmail.com")
os.environ.setdefault("EMAIL_FROM", "sonyvengala04@gmail.com")

import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from backend.app.core.config import settings
settings.SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", "sonyvengala04@gmail.com")
settings.EMAIL_FROM = os.environ.get("EMAIL_FROM", "sonyvengala04@gmail.com")

from backend.app.core.database import Base, get_db
from backend.app.main import app

# Create in-memory SQLite engine with StaticPool for thread-safe test isolation
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create all tables before test session and drop after."""
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a transactional test database session rolled back after each test."""
    connection = TEST_ENGINE.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Provide a TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
