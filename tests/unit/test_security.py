"""
Unit tests for app.core.security — password hashing and JWT creation.
"""

import time
from unittest.mock import patch

import jwt
import pytest

from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_differs_from_plain(self):
        hashed = get_password_hash("secret123")
        assert hashed != "secret123"

    def test_verify_correct_password(self):
        hashed = get_password_hash("secret123")
        assert verify_password("secret123", hashed) is True

    def test_verify_wrong_password(self):
        hashed = get_password_hash("secret123")
        assert verify_password("wrong", hashed) is False

    def test_different_hashes_for_same_password(self):
        h1 = get_password_hash("secret123")
        h2 = get_password_hash("secret123")
        assert h1 != h2

    def test_verify_password_empty_string(self):
        hashed = get_password_hash("secret123")
        assert verify_password("", hashed) is False


class TestCreateAccessToken:
    def test_token_contains_payload(self):
        with patch("app.core.security.settings") as mock_settings:
            mock_settings.SECRET_KEY.get_secret_value.return_value = "test-secret"
            mock_settings.ALGORITHM = "HS256"

            data = {
                "sub": "user-123",
                "org_id": "org-456",
                "email": "a@b.com",
                "role": "admin",
            }
            token = create_access_token(data)

            decoded = jwt.decode(token, "test-secret", algorithms=["HS256"])
            assert decoded["sub"] == "user-123"
            assert decoded["org_id"] == "org-456"
            assert decoded["email"] == "a@b.com"
            assert decoded["role"] == "admin"
            assert "exp" in decoded

    def test_token_with_custom_expiry(self):
        from datetime import timedelta

        with patch("app.core.security.settings") as mock_settings:
            mock_settings.SECRET_KEY.get_secret_value.return_value = "test-secret"
            mock_settings.ALGORITHM = "HS256"

            data = {"sub": "user-123"}
            token = create_access_token(data, expires_delta=timedelta(hours=1))

            decoded = jwt.decode(token, "test-secret", algorithms=["HS256"])
            assert decoded["sub"] == "user-123"
            assert "exp" in decoded

    def test_token_default_expiry_is_15_minutes(self):
        with patch("app.core.security.settings") as mock_settings:
            mock_settings.SECRET_KEY.get_secret_value.return_value = "test-secret"
            mock_settings.ALGORITHM = "HS256"

            before = time.time()
            token = create_access_token({"sub": "u"})
            after = time.time()

            decoded = jwt.decode(token, "test-secret", algorithms=["HS256"])
            exp = decoded["exp"]
            assert (exp - before) <= 15 * 60 + 2
            assert (exp - after) >= 15 * 60 - 2

    def test_token_does_not_mutate_input_dict(self):
        with patch("app.core.security.settings") as mock_settings:
            mock_settings.SECRET_KEY.get_secret_value.return_value = "test-secret"
            mock_settings.ALGORITHM = "HS256"

            data = {"sub": "user-123"}
            original = data.copy()
            create_access_token(data)
            assert data == original
