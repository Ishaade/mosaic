"""
Shared fixtures for tests.

Uses an in-memory SQLite DB so tests never touch mosaic.db or need an API key.
Phase 3 tests that need vectors use an EphemeralClient MemoryStore with a
unique collection name (Chroma's ephemeral client is shared process-wide).
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.services.distress_classifier import DistressResult
from app.services.memory_store import MemoryStore, set_memory_store


@pytest.fixture()
def mock_distress_classifier():
    """
    Phase 4: /chat calls an LLM classifier after keywords.
    Default mock = not crisis so tests need no API key.
    Override in a test when you want layer-2 to fire.
    """
    with patch(
        "app.services.distress_classifier.classify_distress",
        new_callable=AsyncMock,
        return_value=DistressResult(
            crisis=False, confidence="high", reason="test-default"
        ),
    ) as mocked:
        yield mocked


@pytest.fixture()
def mem_store():
    """Isolated ephemeral Chroma collection for tests that touch memories."""
    store = MemoryStore(
        ephemeral=True,
        collection_name=f"test_{uuid.uuid4().hex}",
    )
    set_memory_store(store)
    yield store
    set_memory_store(None)

# StaticPool: one shared in-memory connection so all sessions see the same tables
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
    """HTTP client with DB override + mocked distress classifier (no API key)."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    set_memory_store(None)  # don't leak ephemeral stores across tests
