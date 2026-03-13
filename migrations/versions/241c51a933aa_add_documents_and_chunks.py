"""add_documents_and_chunks

Revision ID: 241c51a933aa
Revises: 3965d568daa9
Create Date: 2026-03-13 23:45:08.190974

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '241c51a933aa'
down_revision: Union[str, Sequence[str], None] = '3965d568daa9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add as nullable (IF NOT EXISTS handles any partial state)
    op.execute(
        "ALTER TABLE orgs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE")
    op.execute(
        "ALTER TABLE kbs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE")
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE")

    # Backfill
    op.execute("UPDATE orgs SET updated_at = created_at WHERE updated_at IS NULL")
    op.execute("UPDATE kbs SET updated_at = created_at WHERE updated_at IS NULL")
    op.execute("UPDATE users SET updated_at = created_at WHERE updated_at IS NULL")

    # Enforce NOT NULL
    op.alter_column('orgs', 'updated_at', nullable=False)
    op.alter_column('kbs', 'updated_at', nullable=False)
    op.alter_column('users', 'updated_at', nullable=False)

    # Fix created_at timezone
    op.alter_column('kbs', 'created_at', existing_type=postgresql.TIMESTAMP(
    ), type_=sa.DateTime(timezone=True), existing_nullable=False)
    op.alter_column('orgs', 'created_at', existing_type=postgresql.TIMESTAMP(
    ), type_=sa.DateTime(timezone=True), existing_nullable=False)
    op.alter_column('users', 'created_at', existing_type=postgresql.TIMESTAMP(
    ), type_=sa.DateTime(timezone=True), existing_nullable=False)

    op.drop_index(op.f('ix_users_id'), table_name='users', if_exists=True)


def downgrade() -> None:
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.alter_column('users', 'created_at', existing_type=sa.DateTime(
        timezone=True), type_=postgresql.TIMESTAMP(), existing_nullable=False)
    op.drop_column('users', 'updated_at')
    op.alter_column('orgs', 'created_at', existing_type=sa.DateTime(
        timezone=True), type_=postgresql.TIMESTAMP(), existing_nullable=False)
    op.drop_column('orgs', 'updated_at')
    op.alter_column('kbs', 'created_at', existing_type=sa.DateTime(
        timezone=True), type_=postgresql.TIMESTAMP(), existing_nullable=False)
    op.drop_column('kbs', 'updated_at')
