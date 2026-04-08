"""
Shared fixtures for document endpoint tests.

Uses an in-memory SQLite DB (via aiosqlite) so tests never touch the real
PostgreSQL instance, and patches external services (storage, Celery) at the
module boundary.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base, get_db
from app.api.deps import get_current_user
from app.schemas.auth import UserContext


# ---------------------------------------------------------------------------
# Shared IDs used across fixtures
# ---------------------------------------------------------------------------
TEST_USER_ID = uuid.uuid4()
TEST_ORG_ID = uuid.uuid4()
TEST_KB_ID = uuid.uuid4()
TEST_EMAIL = "testuser@example.com"


# ---------------------------------------------------------------------------
# Async SQLite engine & session (in-memory, fast)
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine_test = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=engine_test, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test, drop afterwards."""
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ---------------------------------------------------------------------------
# DB session override
# ---------------------------------------------------------------------------
async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Auth override – returns a deterministic UserContext
# ---------------------------------------------------------------------------
def override_get_current_user():
    return UserContext(
        user_id=TEST_USER_ID,
        org_id=TEST_ORG_ID,
        email=TEST_EMAIL,
    )


# ---------------------------------------------------------------------------
# Seed a KnowledgeBase row so the upload endpoint doesn't 400
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture()
async def seed_kb():
    """Insert a KnowledgeBase row matching the test org."""
    from app.models.knowledgebase import KnowledgeBase

    async with TestSessionLocal() as session:
        kb = KnowledgeBase(
            id=TEST_KB_ID,
            name="Default KB",
            org_id=TEST_ORG_ID,
        )
        session.add(kb)
        await session.commit()
    return TEST_KB_ID


# ---------------------------------------------------------------------------
# Seed a Document row for status-check tests
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture()
async def seed_document(seed_kb):
    """Insert a Document row with status=PENDING."""
    from app.models.document import Document

    doc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    async with TestSessionLocal() as session:
        doc = Document(
            id=doc_id,
            org_id=TEST_ORG_ID,
            kb_id=TEST_KB_ID,
            source_type="file",
            filename="test_report.pdf",
            file_path=f"uploads/{doc_id}.pdf",
            status="pending",
            created_at=now,
            updated_at=now,
        )
        session.add(doc)
        await session.commit()
    return doc_id


# ---------------------------------------------------------------------------
# Async HTTP client wired to the FastAPI app
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture()
async def client():
    """
    Yields an httpx.AsyncClient already connected to the FastAPI app with
    dependency overrides applied.
    """
    from app.main import app

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()
