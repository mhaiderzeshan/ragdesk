"""
pgvector-based semantic search with tenant isolation.
Always filters by org_id AND kb_id before returning chunks.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models.chunk import Chunk
from app.models.document import Document

if TYPE_CHECKING:
    pass


async def search_similar_chunks(
    db: AsyncSession,
    kb_id: uuid.UUID | str,
    org_id: uuid.UUID | str,
    query_embedding: list[float],
    top_k: int = 6,
) -> list[dict]:
    """
    Cosine similarity search via pgvector (<=> operator = cosine distance).

    Returns a list of dicts with keys:
        chunk_id, document_id, text, score, metadata_jsonb

    Security: Both org_id and kb_id filters are applied at the DB level,
    preventing cross-tenant leakage even if application logic is bypassed.
    """
    # Build the query using pgvector's <=> (cosine distance) operator.
    # We join through documents to guarantee kb/org scoping.
    stmt = (
        select(
            Chunk.id.label("chunk_id"),
            Chunk.document_id,
            Chunk.text,
            Chunk.metadata_jsonb,
            # cosine similarity = 1 - cosine distance
            (1 - Chunk.embedding.op("<=>")(query_embedding)).label("score"),
        )
        .join(Document, Chunk.document_id == Document.id)
        .where(
            Document.kb_id == kb_id,
            Document.org_id == org_id,
            Chunk.org_id == org_id,         # denormalized, still checked
        )
        .order_by(text("score DESC"))
        .limit(top_k)
    )

    result = await db.execute(stmt)
    rows = result.mappings().all()

    return [
        {
            "chunk_id": str(row["chunk_id"]),
            "document_id": str(row["document_id"]),
            "text": row["text"],
            "score": float(row["score"]),
            "metadata_jsonb": row["metadata_jsonb"],
        }
        for row in rows
    ]
