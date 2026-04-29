"""Add file_path and error_msg to Document

Revision ID: 6cfa6b6665f6
Revises: 5e60b7203ca9
Create Date: 2026-04-07 11:17:37.316707

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6cfa6b6665f6'
down_revision: Union[str, Sequence[str], None] = 'e3a7f1b2c4d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('documents', sa.Column('file_path', sa.String(length=1024), nullable=True))
    op.add_column('documents', sa.Column('error_msg', sa.String(length=1024), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('documents', 'error_msg')
    op.drop_column('documents', 'file_path')
