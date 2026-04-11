"""
End-to-end tests for /eval/run endpoint (admin only).
"""

import uuid
from unittest.mock import patch, AsyncMock

import pytest

from tests.conftest import TEST_KB_ID


class TestEvalRun:
    @pytest.mark.asyncio
    async def test_eval_run_success(self, admin_client, seed_kb):
        fake_embedding = [0.1] * 1536
        doc_id = str(uuid.uuid4())
        fake_chunks = [
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": doc_id,
                "text": "Some content.",
                "score": 0.9,
            }
        ]

        with (
            patch("app.api.endpoints.eval._embed_query", return_value=fake_embedding),
            patch(
                "app.api.endpoints.eval.search_similar_chunks", return_value=fake_chunks
            ),
            patch("app.api.endpoints.eval.log_action", new_callable=AsyncMock),
        ):
            response = await admin_client.post(
                "/eval/run",
                json={
                    "kb_id": str(TEST_KB_ID),
                    "dataset": [
                        {
                            "question": "What is RAG?",
                            "expected_document_ids": [doc_id],
                        }
                    ],
                    "top_k": 6,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["total_questions"] == 1
        assert body["hit_rate"] == 1.0
        assert body["mrr"] == 1.0
        assert len(body["results"]) == 1
        assert body["results"][0]["hit"] is True
        assert body["results"][0]["rr"] == 1.0

    @pytest.mark.asyncio
    async def test_eval_run_no_hits(self, admin_client, seed_kb):
        fake_embedding = [0.1] * 1536
        wrong_doc_id = str(uuid.uuid4())
        expected_doc_id = str(uuid.uuid4())
        fake_chunks = [
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": wrong_doc_id,
                "text": "Irrelevant content.",
                "score": 0.5,
            }
        ]

        with (
            patch("app.api.endpoints.eval._embed_query", return_value=fake_embedding),
            patch(
                "app.api.endpoints.eval.search_similar_chunks", return_value=fake_chunks
            ),
            patch("app.api.endpoints.eval.log_action", new_callable=AsyncMock),
        ):
            response = await admin_client.post(
                "/eval/run",
                json={
                    "kb_id": str(TEST_KB_ID),
                    "dataset": [
                        {
                            "question": "What is RAG?",
                            "expected_document_ids": [expected_doc_id],
                        }
                    ],
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["hit_rate"] == 0.0
        assert body["mrr"] == 0.0
        assert body["results"][0]["hit"] is False

    @pytest.mark.asyncio
    async def test_eval_run_empty_dataset_returns_400(self, admin_client, seed_kb):
        with patch("app.api.endpoints.eval.log_action", new_callable=AsyncMock):
            response = await admin_client.post(
                "/eval/run",
                json={
                    "kb_id": str(TEST_KB_ID),
                    "dataset": [],
                },
            )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_eval_run_non_admin_forbidden(self, client, seed_kb):
        response = await client.post(
            "/eval/run",
            json={
                "kb_id": str(TEST_KB_ID),
                "dataset": [
                    {
                        "question": "test",
                        "expected_document_ids": [str(uuid.uuid4())],
                    }
                ],
            },
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_eval_run_multiple_questions(self, admin_client, seed_kb):
        fake_embedding = [0.1] * 1536
        doc_id_1 = str(uuid.uuid4())
        doc_id_2 = str(uuid.uuid4())
        wrong_id = str(uuid.uuid4())

        call_count = 0

        def mock_retrieve(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [
                    {
                        "chunk_id": str(uuid.uuid4()),
                        "document_id": doc_id_1,
                        "text": "T1",
                        "score": 0.9,
                    }
                ]
            return [
                {
                    "chunk_id": str(uuid.uuid4()),
                    "document_id": wrong_id,
                    "text": "T2",
                    "score": 0.5,
                }
            ]

        with (
            patch("app.api.endpoints.eval._embed_query", return_value=fake_embedding),
            patch(
                "app.api.endpoints.eval.search_similar_chunks",
                side_effect=mock_retrieve,
            ),
            patch("app.api.endpoints.eval.log_action", new_callable=AsyncMock),
        ):
            response = await admin_client.post(
                "/eval/run",
                json={
                    "kb_id": str(TEST_KB_ID),
                    "dataset": [
                        {"question": "Q1", "expected_document_ids": [doc_id_1]},
                        {"question": "Q2", "expected_document_ids": [doc_id_2]},
                    ],
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["total_questions"] == 2
        assert body["hit_rate"] == 0.5
        assert body["mrr"] == 0.5
