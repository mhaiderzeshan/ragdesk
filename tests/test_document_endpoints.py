"""
Tests for POST /documents/upload  and  GET /documents/{document_id}/status

All external I/O (disk writes, Celery) is mocked so the suite runs fast,
offline, and without Docker.
"""

import io
import uuid
from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import TEST_ORG_ID, TEST_KB_ID, _fake_tasks


# ========================================================================
# POST /documents/upload — happy-path
# ========================================================================
class TestUploadDocument:
    """Covers the upload endpoint under various conditions."""

    @pytest.mark.asyncio
    async def test_upload_success(self, client, seed_kb):
        fake_doc_id = str(uuid.uuid4())
        fake_path = f"uploads/{fake_doc_id}.pdf"

        _fake_tasks.process_document.reset_mock()

        with patch(
            "app.api.endpoints.document.save_upload",
            return_value=(fake_doc_id, fake_path),
        ):
            file_content = b"%PDF-1.4 fake content"
            response = await client.post(
                "/documents/upload",
                files={
                    "file": ("report.pdf", io.BytesIO(file_content), "application/pdf")
                },
            )

        assert response.status_code == 202
        body = response.json()
        assert body["document_id"] == fake_doc_id
        assert body["filename"] == "report.pdf"
        assert body["status"] == "PENDING"
        assert "message" in body

    @pytest.mark.asyncio
    async def test_upload_no_knowledgebase_returns_400(self, client):
        with patch(
            "app.api.endpoints.document.save_upload",
            return_value=(str(uuid.uuid4()), "uploads/x.pdf"),
        ):
            response = await client.post(
                "/documents/upload",
                files={"file": ("doc.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
            )

        assert response.status_code == 400
        assert "No Knowledge Base" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_invalid_extension_returns_400(self, client, seed_kb):
        from fastapi import HTTPException

        with patch(
            "app.api.endpoints.document.save_upload",
            side_effect=HTTPException(
                status_code=400,
                detail="File type '.exe' is not allowed.",
            ),
        ):
            response = await client.post(
                "/documents/upload",
                files={
                    "file": (
                        "malware.exe",
                        io.BytesIO(b"MZ"),
                        "application/octet-stream",
                    )
                },
            )

        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_celery_failure_returns_503(self, client, seed_kb):
        fake_doc_id = str(uuid.uuid4())
        fake_path = f"uploads/{fake_doc_id}.pdf"

        _fake_tasks.process_document.delay = MagicMock(
            side_effect=ConnectionError("Redis refused")
        )

        with patch(
            "app.api.endpoints.document.save_upload",
            return_value=(fake_doc_id, fake_path),
        ):
            response = await client.post(
                "/documents/upload",
                files={"file": ("slides.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
            )

        _fake_tasks.process_document.delay = MagicMock()

        assert response.status_code == 503
        assert "Failed to enqueue" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_empty_file_returns_400(self, client, seed_kb):
        from fastapi import HTTPException

        with patch(
            "app.api.endpoints.document.save_upload",
            side_effect=HTTPException(
                status_code=400, detail="Uploaded file is empty."
            ),
        ):
            response = await client.post(
                "/documents/upload",
                files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
            )

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_upload_oversized_file_returns_413(self, client, seed_kb):
        from fastapi import HTTPException

        with patch(
            "app.api.endpoints.document.save_upload",
            side_effect=HTTPException(
                status_code=413,
                detail="File size 15.0MB exceeds the limit of 10MB.",
            ),
        ):
            response = await client.post(
                "/documents/upload",
                files={"file": ("huge.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
            )

        assert response.status_code == 413
        assert "exceeds" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_upload_missing_file_field_returns_422(self, client, seed_kb):
        response = await client.post("/documents/upload")
        assert response.status_code == 422


# ========================================================================
# GET /documents/{document_id}/status
# ========================================================================
class TestGetDocumentStatus:
    """Covers the document status-polling endpoint."""

    @pytest.mark.asyncio
    async def test_status_existing_document(self, client, seed_document):
        response = await client.get(f"/documents/{seed_document}/status")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "pending"
        assert body["filename"] == "test_report.pdf"

    @pytest.mark.asyncio
    async def test_status_nonexistent_document_returns_404(self, client, seed_kb):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/documents/{fake_id}/status")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
