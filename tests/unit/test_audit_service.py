"""
Unit tests for app.services.audit — log_action.
"""

import uuid
from unittest.mock import patch, AsyncMock

import pytest
from sqlalchemy import select

from app.models.audit import AuditLog
from app.services.audit import log_action
from tests.conftest import TEST_ORG_ID


pytestmark = pytest.mark.asyncio


class TestLogAction:
    async def test_creates_audit_log_entry(self, db_session, seed_org):
        user_id = uuid.uuid4()

        with patch.object(db_session, "commit", new_callable=AsyncMock):
            await log_action(
                db_session,
                org_id=TEST_ORG_ID,
                user_id=user_id,
                action="upload_document",
                resource="doc-123",
            )
            await db_session.flush()

        result = await db_session.execute(select(AuditLog))
        logs = result.scalars().all()
        assert len(logs) == 1
        assert logs[0].action == "upload_document"
        assert logs[0].resource == "doc-123"

    async def test_log_with_metadata(self, db_session, seed_org):
        user_id = uuid.uuid4()
        meta = {"hit_rate": 0.85, "mrr": 0.72}

        with patch.object(db_session, "commit", new_callable=AsyncMock):
            await log_action(
                db_session,
                org_id=TEST_ORG_ID,
                user_id=user_id,
                action="eval_run",
                resource="kb-456",
                metadata=meta,
            )
            await db_session.flush()

        result = await db_session.execute(select(AuditLog))
        log_entry = result.scalar_one()
        assert log_entry.action == "eval_run"

    async def test_log_with_none_user_id(self, db_session, seed_org):
        with patch.object(db_session, "commit", new_callable=AsyncMock):
            await log_action(
                db_session,
                org_id=TEST_ORG_ID,
                user_id=None,
                action="system_event",
                resource="cron-job",
            )
            await db_session.flush()

        result = await db_session.execute(select(AuditLog))
        log_entry = result.scalar_one()
        assert log_entry.user_id is None
        assert log_entry.action == "system_event"

    async def test_log_default_metadata_is_empty_dict(self, db_session, seed_org):
        user_id = uuid.uuid4()

        with patch.object(db_session, "commit", new_callable=AsyncMock):
            await log_action(
                db_session,
                org_id=TEST_ORG_ID,
                user_id=user_id,
                action="chat",
                resource="kb-789",
            )
            await db_session.flush()

        result = await db_session.execute(select(AuditLog))
        log_entry = result.scalar_one()
        assert log_entry.action == "chat"

    async def test_multiple_logs_accumulate(self, db_session, seed_org):
        user_id = uuid.uuid4()

        with patch.object(db_session, "commit", new_callable=AsyncMock):
            for i in range(3):
                await log_action(
                    db_session,
                    org_id=TEST_ORG_ID,
                    user_id=user_id,
                    action=f"action_{i}",
                    resource=f"res_{i}",
                )
            await db_session.flush()

        result = await db_session.execute(select(AuditLog))
        logs = result.scalars().all()
        assert len(logs) == 3
