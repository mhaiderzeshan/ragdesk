"""
pgvector-based semantic search with tenant isolation.
Always filters by org_id AND kb_id before returning chunks.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models.chunk import Chunk
from app.models.document import Document

if TYPE_CHECKING:
    pass


def _vector_literal(embedding: list[float]) -> str:
    """Format a Python list as a pgvector string literal: '[0.1,0.2,...]'"""
    return "'" + "[" + ",".join(str(v) for v in embedding) + "]" + "'"


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
    # Use raw SQL with an inline vector literal instead of a parameter.
    # This avoids asyncpg mis-serializing a Python list as a multi-dimensional
    # array (which causes pgvector's "expected ndim to be 1" error).
    vec_str = _vector_literal(query_embedding)

    sql = text(f"""
        SELECT
            chunks.id   AS chunk_id,
            chunks.document_id,
            chunks.text,
            chunks.metadata_jsonb,
            (1 - (chunks.embedding <=> {vec_str}::vector)) AS score
        FROM chunks
        JOIN documents ON chunks.document_id = documents.id
        WHERE documents.kb_id   = :kb_id
          AND documents.org_id  = :org_id
          AND chunks.org_id     = :org_id2
        ORDER BY score DESC
        LIMIT :limit
    """)

    result = await db.execute(
        sql,
        {
            "kb_id": str(kb_id),
            "org_id": str(org_id),
            "org_id2": str(org_id),
            "limit": top_k,
        },
    )
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
