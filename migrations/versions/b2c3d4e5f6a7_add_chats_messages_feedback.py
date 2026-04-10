"""add chats messages feedback tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-09 13:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- chats --
    op.create_table(
        'chats',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('orgs.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('kb_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('kbs.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('ix_chats_org_id', 'chats', ['org_id'])
    op.create_index('ix_chats_user_id', 'chats', ['user_id'])
    op.create_index('ix_chats_kb_id', 'chats', ['kb_id'])

    # -- messages --
    op.create_table(
        'messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('chat_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('chats.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('retrieved_chunk_ids', postgresql.JSONB,
                  server_default='[]', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('ix_messages_chat_id', 'messages', ['chat_id'])

    # -- feedback --
    op.create_table(
        'feedback',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('message_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('messages.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('rating', sa.Integer, nullable=False),
        sa.Column('note', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('ix_feedback_message_id', 'feedback', ['message_id'])


def downgrade() -> None:
    op.drop_table('feedback')
    op.drop_table('messages')
    op.drop_table('chats')
