"""
Unit tests for app.api.deps — JWT decoding and user context extraction.
"""

import uuid
from unittest.mock import patch, AsyncMock

import jwt
import pytest

from app.api.deps import get_current_user
from app.schemas.auth import UserContext


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_valid_token_returns_user_context(self):
        user_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())

        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.SECRET_KEY.get_secret_value.return_value = "test-secret"
            mock_settings.ALGORITHM = "HS256"

            token = jwt.encode(
                {"sub": user_id, "org_id": org_id, "email": "a@b.com", "role": "admin"},
                "test-secret",
                algorithm="HS256",
            )

            mock_db = AsyncMock()
            result = await get_current_user(token=token, db=mock_db)

        assert isinstance(result, UserContext)
        assert str(result.user_id) == user_id
        assert str(result.org_id) == org_id
        assert result.email == "a@b.com"
        assert result.role == "admin"

    @pytest.mark.asyncio
    async def test_missing_sub_raises_401(self):
        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.SECRET_KEY.get_secret_value.return_value = "test-secret"
            mock_settings.ALGORITHM = "HS256"

            token = jwt.encode(
                {"org_id": str(uuid.uuid4()), "email": "a@b.com"},
                "test-secret",
                algorithm="HS256",
            )

            mock_db = AsyncMock()
            with pytest.raises(Exception) as exc_info:
                await get_current_user(token=token, db=mock_db)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_org_id_raises_401(self):
        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.SECRET_KEY.get_secret_value.return_value = "test-secret"
            mock_settings.ALGORITHM = "HS256"

            token = jwt.encode(
                {"sub": str(uuid.uuid4()), "email": "a@b.com"},
                "test-secret",
                algorithm="HS256",
            )

            mock_db = AsyncMock()
            with pytest.raises(Exception) as exc_info:
                await get_current_user(token=token, db=mock_db)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.SECRET_KEY.get_secret_value.return_value = "test-secret"
            mock_settings.ALGORITHM = "HS256"

            mock_db = AsyncMock()
            with pytest.raises(Exception) as exc_info:
                await get_current_user(token="invalid.jwt.token", db=mock_db)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_default_role_is_user(self):
        user_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())

        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.SECRET_KEY.get_secret_value.return_value = "test-secret"
            mock_settings.ALGORITHM = "HS256"

            token = jwt.encode(
                {"sub": user_id, "org_id": org_id, "email": "a@b.com"},
                "test-secret",
                algorithm="HS256",
            )

            mock_db = AsyncMock()
            result = await get_current_user(token=token, db=mock_db)

        assert result.role == "user"
