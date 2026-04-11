"""
End-to-end tests for /feedback endpoint.
"""

import uuid

import pytest

from tests.conftest import TEST_ORG_ID


class TestSubmitFeedback:
    @pytest.mark.asyncio
    async def test_thumbs_up_feedback(self, client, seed_chat_and_message):
        chat_id, msg_id = seed_chat_and_message
        response = await client.post(
            "/feedback",
            json={"message_id": msg_id, "rating": 1},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["rating"] == 1
        assert body["message_id"] == msg_id

    @pytest.mark.asyncio
    async def test_thumbs_down_feedback(self, client, seed_chat_and_message):
        chat_id, msg_id = seed_chat_and_message
        response = await client.post(
            "/feedback",
            json={"message_id": msg_id, "rating": -1},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["rating"] == -1

    @pytest.mark.asyncio
    async def test_feedback_with_note(self, client, seed_chat_and_message):
        chat_id, msg_id = seed_chat_and_message
        response = await client.post(
            "/feedback",
            json={"message_id": msg_id, "rating": 1, "note": "Very helpful!"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["note"] == "Very helpful!"

    @pytest.mark.asyncio
    async def test_feedback_nonexistent_message_returns_404(self, client, seed_kb):
        fake_msg_id = str(uuid.uuid4())
        response = await client.post(
            "/feedback",
            json={"message_id": fake_msg_id, "rating": 1},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_feedback_invalid_rating_returns_422(
        self, client, seed_chat_and_message
    ):
        chat_id, msg_id = seed_chat_and_message
        response = await client.post(
            "/feedback",
            json={"message_id": msg_id, "rating": 5},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_feedback_missing_message_id_returns_422(
        self, client, seed_chat_and_message
    ):
        response = await client.post(
            "/feedback",
            json={"rating": 1},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_feedback_note_too_long_returns_422(
        self, client, seed_chat_and_message
    ):
        chat_id, msg_id = seed_chat_and_message
        response = await client.post(
            "/feedback",
            json={"message_id": msg_id, "rating": 1, "note": "x" * 2001},
        )
        assert response.status_code == 422
