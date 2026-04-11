"""
Unit tests for app.services.document — CRUD operations.
"""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.document import Document
from app.services.document import (
    create_document_record,
    get_document_by_id,
    update_document_status,
)
from tests.conftest import TEST_ORG_ID, TEST_KB_ID


pytestmark = pytest.mark.asyncio


class TestCreateDocumentRecord:
    async def test_creates_document_with_pending_status(self, db_session, seed_kb):
        doc_id = str(uuid.uuid4())
        doc = await create_document_record(
            db=db_session,
            document_id=doc_id,
            org_id=str(TEST_ORG_ID),
            kb_id=str(TEST_KB_ID),
            filename="test.pdf",
            file_path=f"uploads/{doc_id}.pdf",
        )

        assert doc.id == doc_id
        assert doc.status == "pending"
        assert doc.filename == "test.pdf"
        assert doc.source_type == "file"

    async def test_created_document_is_queryable(self, db_session, seed_kb):
        doc_id = str(uuid.uuid4())
        await create_document_record(
            db=db_session,
            document_id=doc_id,
            org_id=str(TEST_ORG_ID),
            kb_id=str(TEST_KB_ID),
            filename="report.pdf",
            file_path=f"uploads/{doc_id}.pdf",
        )
        await db_session.flush()

        result = await db_session.execute(select(Document).where(Document.id == doc_id))
        found = result.scalar_one()
        assert found.filename == "report.pdf"


class TestGetDocumentById:
    async def test_returns_existing_document(self, db_session, seed_document):
        doc = await get_document_by_id(db_session, seed_document)
        assert str(doc.id) == seed_document

    async def test_raises_404_for_nonexistent_id(self, db_session):
        fake_id = str(uuid.uuid4())
        with pytest.raises(HTTPException) as exc_info:
            await get_document_by_id(db_session, fake_id)
        assert exc_info.value.status_code == 404


class TestUpdateDocumentStatus:
    async def test_update_to_processing(self, db_session, seed_document):
        doc = await update_document_status(db_session, seed_document, "processing")
        assert doc.status == "processing"

    async def test_update_to_completed(self, db_session, seed_document):
        doc = await update_document_status(db_session, seed_document, "completed")
        assert doc.status == "completed"

    async def test_update_to_failed_with_error_msg(self, db_session, seed_document):
        doc = await update_document_status(
            db_session, seed_document, "failed", error_msg="Out of memory"
        )
        assert doc.status == "failed"
        assert doc.error_msg == "Out of memory"

    async def test_update_nonexistent_raises_404(self, db_session):
        fake_id = str(uuid.uuid4())
        with pytest.raises(HTTPException) as exc_info:
            await update_document_status(db_session, fake_id, "processing")
        assert exc_info.value.status_code == 404
