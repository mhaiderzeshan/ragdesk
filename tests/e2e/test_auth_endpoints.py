"""
End-to-end tests for /auth/* endpoints — register, login, me.
"""

import uuid
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from tests.conftest import TEST_ORG_ID, TEST_USER_ID, TEST_EMAIL


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_success_returns_201(self, client):
        with patch("app.services.auth.AuthService.register_new_org") as mock_reg:
            from app.models.user import User

            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.email = "newuser@example.com"
            mock_user.org_id = uuid.uuid4()
            mock_user.role = "admin"
            mock_reg.return_value = mock_user

            response = await client.post(
                "/auth/register",
                json={
                    "org_name": "New Org",
                    "email": "newuser@example.com",
                    "password": "securepass123",
                },
            )

        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "newuser@example.com"
        assert body["role"] == "admin"

    @pytest.mark.asyncio
    async def test_register_missing_fields_returns_422(self, client):
        response = await client.post("/auth/register", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_email_returns_422(self, client):
        response = await client.post(
            "/auth/register",
            json={
                "org_name": "Org",
                "email": "not-an-email",
                "password": "securepass123",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_duplicate_email_returns_400(self, client):
        from sqlalchemy.exc import IntegrityError

        with patch("app.services.auth.AuthService.register_new_org") as mock_reg:
            mock_orig = MagicMock()
            mock_orig.__str__ = lambda self: "duplicate key value violates unique constraint users_email_key"
            mock_reg.side_effect = IntegrityError("duplicate key", params=None, orig=mock_orig)

            response = await client.post(
                "/auth/register",
                json={
                    "org_name": "Dup Org",
                    "email": "dup@example.com",
                    "password": "securepass123",
                },
            )

        assert response.status_code == 400


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, client):
        from app.models.user import User

        with patch("app.services.auth.AuthService.authenticate_user") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.org_id = uuid.uuid4()
            mock_user.email = "user@example.com"
            mock_user.role = "user"
            mock_auth.return_value = mock_user

            with patch("app.services.auth.AuthService.create_user_token") as mock_token:
                mock_token.return_value = "fake-jwt-token"

                response = await client.post(
                    "/auth/login",
                    data={"username": "user@example.com", "password": "secret123"},
                )

        assert response.status_code == 200
        body = response.json()
        assert body["access_token"] == "fake-jwt-token"
        assert body["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_credentials_returns_401(self, client):
        with patch("app.services.auth.AuthService.authenticate_user") as mock_auth:
            mock_auth.return_value = None

            response = await client.post(
                "/auth/login",
                data={"username": "user@example.com", "password": "wrong"},
            )

        assert response.status_code == 401
        assert "Incorrect" in response.json()["detail"]


class TestMe:
    @pytest.mark.asyncio
    async def test_me_returns_user_context(self, client):
        response = await client.get("/auth/me")
        assert response.status_code == 200
        body = response.json()
        assert body["email"] == TEST_EMAIL
        assert body["role"] == "user"

    @pytest.mark.asyncio
    async def test_me_includes_user_id_and_org_id(self, client):
        response = await client.get("/auth/me")
        body = response.json()
        assert body["user_id"] is not None
        assert body["org_id"] is not None
