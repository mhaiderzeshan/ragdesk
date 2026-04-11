"""
End-to-end tests for /kbs/* endpoints — CRUD knowledge bases.
"""

import uuid

import pytest

from tests.conftest import TEST_ORG_ID


class TestCreateKB:
    @pytest.mark.asyncio
    async def test_create_kb_success_returns_201(self, client, seed_kb):
        response = await client.post(
            "/kbs",
            json={"name": "Research Papers"},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Research Papers"
        assert body["org_id"] is not None

    @pytest.mark.asyncio
    async def test_create_kb_empty_name_returns_422(self, client, seed_kb):
        response = await client.post(
            "/kbs",
            json={"name": ""},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_kb_too_long_name_returns_422(self, client, seed_kb):
        response = await client.post(
            "/kbs",
            json={"name": "x" * 256},
        )
        assert response.status_code == 422


class TestListKBs:
    @pytest.mark.asyncio
    async def test_list_kbs_returns_existing(self, client, seed_kb):
        response = await client.get("/kbs")
        assert response.status_code == 200
        body = response.json()
        assert len(body) >= 1
        assert body[0]["name"] == "Default KB"

    @pytest.mark.asyncio
    async def test_list_kbs_scoped_to_org(self, client, seed_kb):
        response = await client.get("/kbs")
        body = response.json()
        for kb in body:
            assert kb["org_id"] is not None


class TestGetKB:
    @pytest.mark.asyncio
    async def test_get_existing_kb(self, client, seed_kb):
        response = await client.get(f"/kbs/{seed_kb}")
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Default KB"
        assert body["id"] is not None

    @pytest.mark.asyncio
    async def test_get_nonexistent_kb_returns_404(self, client, seed_kb):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/kbs/{fake_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_kb_includes_created_at(self, client, seed_kb):
        response = await client.get(f"/kbs/{seed_kb}")
        body = response.json()
        assert "created_at" in body
