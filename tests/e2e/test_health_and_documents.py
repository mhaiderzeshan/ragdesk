"""
End-to-end tests for /health endpoint and /documents listing.
"""

import uuid
from unittest.mock import MagicMock

import pytest


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestListDocuments:
    @pytest.mark.asyncio
    async def test_list_documents_empty(self, client, seed_kb):
        response = await client.get("/documents")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_documents_with_seeded_doc(self, client, seed_document):
        response = await client.get("/documents")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["filename"] == "test_report.pdf"
        assert body[0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_documents_scoped_to_org(self, client, seed_document):
        response = await client.get("/documents")
        body = response.json()
        for doc in body:
            assert doc["kb_id"] is not None


class TestDocumentReindex:
    @pytest.mark.asyncio
    async def test_reindex_success(self, client, seed_document):
        from tests.conftest import _fake_tasks

        _fake_tasks.process_document.delay = MagicMock()

        response = await client.post(f"/documents/{seed_document}/reindex")
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "PENDING"
        assert "Reindex" in body["message"]

    @pytest.mark.asyncio
    async def test_reindex_nonexistent_document(self, client, seed_kb):
        fake_id = str(uuid.uuid4())
        response = await client.post(f"/documents/{fake_id}/reindex")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_reindex_celery_failure(self, client, seed_document):
        from tests.conftest import _fake_tasks

        _fake_tasks.process_document.delay = MagicMock(
            side_effect=ConnectionError("Redis down")
        )

        response = await client.post(f"/documents/{seed_document}/reindex")
        assert response.status_code == 503

        _fake_tasks.process_document.delay = MagicMock()
