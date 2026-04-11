"""
Unit tests for app.api.rbac — require_role dependency.
"""

import uuid

import pytest
from fastapi import HTTPException

from app.api.rbac import require_role
from app.schemas.auth import UserContext


class TestRequireRole:
    @pytest.mark.asyncio
    async def test_admin_role_allowed(self):
        dep = require_role("admin")
        user = UserContext(
            user_id=uuid.uuid4(), org_id=uuid.uuid4(), email="a@b.com", role="admin"
        )
        result = await dep(current_user=user)
        assert result == user

    @pytest.mark.asyncio
    async def test_user_role_rejected_for_admin_only(self):
        dep = require_role("admin")
        user = UserContext(
            user_id=uuid.uuid4(), org_id=uuid.uuid4(), email="a@b.com", role="user"
        )
        with pytest.raises(HTTPException) as exc_info:
            await dep(current_user=user)
        assert exc_info.value.status_code == 403
        assert "admin" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_multiple_allowed_roles(self):
        dep = require_role("admin", "editor")
        admin_user = UserContext(
            user_id=uuid.uuid4(), org_id=uuid.uuid4(), email="a@b.com", role="admin"
        )
        result = await dep(current_user=admin_user)
        assert result.role == "admin"

        editor_user = UserContext(
            user_id=uuid.uuid4(), org_id=uuid.uuid4(), email="b@c.com", role="editor"
        )
        result = await dep(current_user=editor_user)
        assert result.role == "editor"

    @pytest.mark.asyncio
    async def test_no_matching_role_raises_403(self):
        dep = require_role("admin", "editor")
        user = UserContext(
            user_id=uuid.uuid4(), org_id=uuid.uuid4(), email="a@b.com", role="viewer"
        )
        with pytest.raises(HTTPException) as exc_info:
            await dep(current_user=user)
        assert exc_info.value.status_code == 403
