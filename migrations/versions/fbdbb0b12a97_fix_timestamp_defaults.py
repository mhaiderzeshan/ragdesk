"""fix_timestamp_defaults

Revision ID: fbdbb0b12a97
Revises: f8dc5711ddff
Create Date: 2026-05-13 05:51:33.275924

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fbdbb0b12a97'
down_revision: Union[str, Sequence[str], None] = 'f8dc5711ddff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    tables = [
        'audit_logs',
        'chats',
        'chunks',
        'documents',
        'feedback',
        'kbs',
        'messages',
        'orgs',
        'users',
    ]
    for table in tables:
        op.alter_column(table, 'created_at', server_default=sa.func.now())


def downgrade() -> None:
    tables = [
        'audit_logs',
        'chats',
        'chunks',
        'documents',
        'feedback',
        'kbs',
        'messages',
        'orgs',
        'users',
    ]
    for table in tables:
        op.alter_column(table, 'created_at', server_default=None)