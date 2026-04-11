"""
Unit tests for app.repositories.auth — AuthRepository.
"""

import uuid

import pytest
from sqlalchemy import select

from app.models.user import User
from app.models.organization import Organization
from app.models.knowledgebase import KnowledgeBase
from app.repositories.auth import AuthRepository
from app.schemas import OrganizationCreate, UserCreate


pytestmark = pytest.mark.asyncio


class TestAuthRepository:
    async def test_create_org_and_user(self, db_session):
        repo = AuthRepository(db_session)
        org_data = OrganizationCreate(name="Test Org")
        user_data = UserCreate(email="user@example.com", password="hashed_pw")

        user = await repo.create_org_and_user(
            org_in=org_data,
            user_in=user_data,
            hashed_password="hashed_pw",
        )

        assert user.email == "user@example.com"
        assert user.hashed_password == "hashed_pw"
        assert user.role == "admin"

    async def test_create_org_creates_default_kb(self, db_session):
        repo = AuthRepository(db_session)
        org_data = OrganizationCreate(name="Org With KB")
        user_data = UserCreate(email="kb_user@example.com", password="hashed_pw")

        await repo.create_org_and_user(
            org_in=org_data,
            user_in=user_data,
            hashed_password="hashed_pw",
        )

        result = await db_session.execute(select(KnowledgeBase))
        kbs = result.scalars().all()
        assert len(kbs) == 1
        assert kbs[0].name == "Default"

    async def test_get_user_by_email_found(self, db_session):
        repo = AuthRepository(db_session)
        org_data = OrganizationCreate(name="Find Org")
        user_data = UserCreate(email="findme@example.com", password="hashed_pw")

        await repo.create_org_and_user(
            org_in=org_data,
            user_in=user_data,
            hashed_password="hashed_pw",
        )

        found = await repo.get_user_by_email("findme@example.com")
        assert found is not None
        assert found.email == "findme@example.com"

    async def test_get_user_by_email_not_found(self, db_session):
        repo = AuthRepository(db_session)
        found = await repo.get_user_by_email("nonexistent@example.com")
        assert found is None

    async def test_first_user_is_admin(self, db_session):
        repo = AuthRepository(db_session)
        org_data = OrganizationCreate(name="Admin Org")
        user_data = UserCreate(email="admin@example.com", password="hashed_pw")

        user = await repo.create_org_and_user(
            org_in=org_data,
            user_in=user_data,
            hashed_password="hashed_pw",
        )
        assert user.role == "admin"
