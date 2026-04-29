"""create_documents_and_chunks_tables

Revision ID: e3a7f1b2c4d9
Revises: 5e60b7203ca9
Create Date: 2026-04-30 04:12:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e3a7f1b2c4d9'
down_revision: Union[str, Sequence[str], None] = '5e60b7203ca9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create documents and chunks tables."""
    import pgvector.sqlalchemy

    # Enable pgvector extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # -- documents --
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('orgs.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('kb_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('kbs.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('status',
                  sa.Enum('pending', 'processing', 'completed', 'failed',
                          name='documentstatus'),
                  nullable=False,
                  server_default='pending'),
        sa.Column('filename', sa.String(255), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('ix_documents_org_id', 'documents', ['org_id'])
    op.create_index('ix_documents_kb_id', 'documents', ['kb_id'])

    # -- chunks --
    # Note: embedding starts at 1536 dims; migration f8dc5711ddff resizes to 768.
    op.create_table(
        'chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('orgs.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('documents.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('chunk_index', sa.Integer, nullable=False),
        sa.Column('text', sa.Text, nullable=False),
        sa.Column('metadata_jsonb', postgresql.JSONB,
                  server_default='{}', nullable=False),
        sa.Column('embedding',
                  pgvector.sqlalchemy.Vector(1536),
                  nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('ix_chunks_org_id', 'chunks', ['org_id'])
    op.create_index('ix_chunks_document_id', 'chunks', ['document_id'])


def downgrade() -> None:
    """Drop documents and chunks tables."""
    op.drop_table('chunks')
    op.drop_table('documents')
    op.execute("DROP TYPE IF EXISTS documentstatus")
