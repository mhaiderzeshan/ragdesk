"""
Shared fixtures for all tests.

Uses an in-memory SQLite DB (via aiosqlite) so tests never touch the real
PostgreSQL instance, and patches external services (storage, Celery) at the
module boundary.
"""

import sys
import uuid
from datetime import datetime, timezone
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, Text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base, get_db
from app.api.deps import get_current_user
from app.schemas.auth import UserContext

# ---------------------------------------------------------------------------
# Stub out the heavy `app.workers.tasks` module so it can be imported without
# Redis / Celery / OpenAI running.
# ---------------------------------------------------------------------------
_fake_tasks = ModuleType("app.workers.tasks")
_fake_tasks.process_document = MagicMock()
sys.modules.setdefault("app.workers.tasks", _fake_tasks)

# ---------------------------------------------------------------------------
# Register SQLite-compatible compilers for PostgreSQL-only column types.
# This lets Base.metadata.create_all() succeed on the in-memory SQLite engine.
# ---------------------------------------------------------------------------
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from pgvector.sqlalchemy import Vector
from sqlalchemy.ext.compiler import compiles


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"


@compiles(Vector, "sqlite")
def _compile_vector_sqlite(type_, compiler, **kw):
    return "BLOB"


@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"


# SQLAlchemy's UUID type calls value.hex in its bind_processor, which breaks
# when the app passes plain strings (as it does — works fine on PostgreSQL).
# Patch the Uuid type so both str and uuid.UUID are accepted on SQLite.
from sqlalchemy import Uuid as SA_Uuid

_original_bind_processor = SA_Uuid.bind_processor


def _patched_bind_processor(self, dialect):
    orig = _original_bind_processor(self, dialect)
    if dialect.name != "sqlite":
        return orig

    def process(value):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(value)

    return process


SA_Uuid.bind_processor = _patched_bind_processor

# Also patch the result_processor so values read back are uuid.UUID objects
_original_result_processor = SA_Uuid.result_processor


def _patched_result_processor(self, dialect, coltype=None):
    if dialect.name != "sqlite":
        return _original_result_processor(self, dialect, coltype)

    def process(value):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))

    return process


SA_Uuid.result_processor = _patched_result_processor


# ---------------------------------------------------------------------------
# Shared IDs used across fixtures
# ---------------------------------------------------------------------------
TEST_USER_ID = uuid.uuid4()
TEST_ORG_ID = uuid.uuid4()
TEST_KB_ID = uuid.uuid4()
TEST_EMAIL = "testuser@example.com"
ADMIN_USER_ID = uuid.uuid4()


# ---------------------------------------------------------------------------
# Async SQLite engine & session (in-memory, fast)
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine_test = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=engine_test, class_=AsyncSession, expire_on_commit=False
)

# SQLite doesn't have a NOW() function — register one so that
# server_default=text("NOW()") on the Document model works.
from sqlalchemy import event as sa_event


@sa_event.listens_for(engine_test.sync_engine, "connect")
def _register_sqlite_now(dbapi_conn, connection_record):
    dbapi_conn.create_function("NOW", 0, lambda: datetime.now(timezone.utc).isoformat())


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
# Auth override – returns a deterministic UserContext (regular user)
# ---------------------------------------------------------------------------
def override_get_current_user():
    return UserContext(
        user_id=TEST_USER_ID,
        org_id=TEST_ORG_ID,
        email=TEST_EMAIL,
        role="user",
    )


# ---------------------------------------------------------------------------
# Auth override – returns admin UserContext
# ---------------------------------------------------------------------------
def override_get_current_admin_user():
    return UserContext(
        user_id=ADMIN_USER_ID,
        org_id=TEST_ORG_ID,
        email="admin@example.com",
        role="admin",
    )


# ---------------------------------------------------------------------------
# Direct DB session fixture (for unit tests that need raw DB access)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture()
async def db_session():
    """Yields a real AsyncSession connected to the test SQLite DB."""
    async with TestSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Seed an Organization row
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture()
async def seed_org():
    """Insert an Organization row."""
    from app.models.organization import Organization

    async with TestSessionLocal() as session:
        org = Organization(id=TEST_ORG_ID, name="Test Org")
        session.add(org)
        await session.commit()
    return TEST_ORG_ID


# ---------------------------------------------------------------------------
# Seed a KnowledgeBase row so the upload endpoint doesn't 400
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture()
async def seed_kb(seed_org):
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

    doc_uuid = uuid.uuid4()
    now = datetime.now(timezone.utc)

    async with TestSessionLocal() as session:
        doc = Document(
            id=doc_uuid,
            org_id=TEST_ORG_ID,
            kb_id=TEST_KB_ID,
            source_type="file",
            filename="test_report.pdf",
            file_path=f"uploads/{doc_uuid}.pdf",
            status="pending",
            created_at=now,
            updated_at=now,
        )
        session.add(doc)
        await session.commit()
    # Return string form — the endpoint receives string path params
    return str(doc_uuid)


# ---------------------------------------------------------------------------
# Seed a Chat + Message pair for feedback tests
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture()
async def seed_chat_and_message(seed_kb):
    """Insert a Chat with a user message and an assistant message."""
    from app.models.chat import Chat
    from app.models.message import Message

    chat_uuid = uuid.uuid4()
    msg_uuid = uuid.uuid4()

    async with TestSessionLocal() as session:
        chat = Chat(
            id=chat_uuid,
            org_id=TEST_ORG_ID,
            user_id=TEST_USER_ID,
            kb_id=TEST_KB_ID,
        )
        session.add(chat)
        await session.flush()

        user_msg = Message(
            id=uuid.uuid4(),
            chat_id=chat_uuid,
            role="user",
            content="What is RAG?",
            retrieved_chunk_ids=[],
        )
        assistant_msg = Message(
            id=msg_uuid,
            chat_id=chat_uuid,
            role="assistant",
            content="RAG stands for Retrieval-Augmented Generation.",
            retrieved_chunk_ids=[],
        )
        session.add_all([user_msg, assistant_msg])
        await session.commit()

    return str(chat_uuid), str(msg_uuid)


# ---------------------------------------------------------------------------
# Async HTTP client wired to the FastAPI app (regular user)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture()
async def client():
    """
    Yields an httpx.AsyncClient already connected to the FastAPI app with
    dependency overrides applied (regular user).
    """
    from app.main import app
    from app.core.rate_limit import limiter

    limiter.enabled = False
    limiter._swallow_errors = True

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()
    limiter.enabled = True
    limiter._swallow_errors = False


# ---------------------------------------------------------------------------
# Async HTTP client wired to the FastAPI app (admin user)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture()
async def admin_client():
    """
    Yields an httpx.AsyncClient with admin user overrides.
    """
    from app.main import app
    from app.core.rate_limit import limiter

    limiter.enabled = False
    limiter._swallow_errors = True

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_admin_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()
    limiter.enabled = True
    limiter._swallow_errors = False
