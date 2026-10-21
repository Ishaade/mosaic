"""
Shared fixtures for tests.

MUST set JWT_SECRET before importing app.config / app.main (no default in Settings).
Uses in-memory SQLite + ephemeral Chroma so tests never touch real data.
"""

import os
import uuid
from unittest.mock import AsyncMock, patch

# Required before Settings() loads — tests never read .env secrets from disk for this
os.environ.setdefault("JWT_SECRET", "pytest-only-jwt-secret-not-for-production")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.rate_limit import limiter
from app.services.distress_classifier import DistressResult
from app.services.memory_store import MemoryStore, set_memory_store


@pytest.fixture(autouse=True)
def _disable_rate_limits():
    """Avoid 429s during the test suite."""
    previous = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = previous


@pytest.fixture()
def mock_distress_classifier():
    with patch(
        "app.services.distress_classifier.classify_distress",
        new_callable=AsyncMock,
        return_value=DistressResult(
            crisis=False, confidence="high", reason="test-default"
        ),
    ) as mocked:
        yield mocked


@pytest.fixture(autouse=True)
def mock_persona_router():
    """
    Stage B: /chat may call the persona router on cooldown turns.
    Default = no suggestion so API tests need no LLM key.
    Override in a test when you want a suggestion.
    """
    with patch(
        "app.routers.chat.suggest_persona",
        new_callable=AsyncMock,
        return_value=None,
    ) as mocked:
        yield mocked


@pytest.fixture()
def mem_store():
    store = MemoryStore(
        ephemeral=True,
        collection_name=f"test_{uuid.uuid4().hex}",
    )
    set_memory_store(store)
    yield store
    set_memory_store(None)


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db, mock_distress_classifier):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    set_memory_store(None)


@pytest.fixture()
def auth_user(client):
    """Default authenticated user + headers for API tests."""
    from tests.helpers import register_and_login

    return register_and_login(client, "user@example.com")


@pytest.fixture()
def other_auth_user(client):
    from tests.helpers import register_and_login

    return register_and_login(client, "other@example.com")
