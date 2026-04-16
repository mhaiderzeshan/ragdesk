"""
pgvector-based semantic search with tenant isolation.
Always filters by org_id AND kb_id before returning chunks.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models.chunk import Chunk
from app.models.document import Document
from app.schemas.chat import RetrievalFilters

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
    filters: Optional[RetrievalFilters] = None,
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

    params = {
        "kb_id": str(kb_id),
        "org_id": str(org_id),
        "org_id2": str(org_id),
        "limit": top_k,
    }

    filter_sql_parts = []

    if filters:
        if filters.page_range:
            if filters.page_range.min_page is not None:
                filter_sql_parts.append(
                    "(chunks.metadata_jsonb->>'page_number')::int >= :min_page"
                )
                params["min_page"] = filters.page_range.min_page
            if filters.page_range.max_page is not None:
                filter_sql_parts.append(
                    "(chunks.metadata_jsonb->>'page_number')::int <= :max_page"
                )
                params["max_page"] = filters.page_range.max_page

        if filters.document_types:
            filter_sql_parts.append(
                "chunks.metadata_jsonb->>'document_type' = ANY(:document_types)"
            )
            params["document_types"] = filters.document_types

        if filters.section_contains:
            filter_sql_parts.append(
                "chunks.metadata_jsonb->>'section_title' ILIKE :section_contains"
            )
            params["section_contains"] = f"%{filters.section_contains}%"

    filter_clause = ""
    if filter_sql_parts:
        filter_clause = " AND " + " AND ".join(filter_sql_parts)

    print(f"[RETRIEVAL DIAG] kb_id={params['kb_id']} org_id={params['org_id']} top_k={top_k}")
    print(f"[RETRIEVAL DIAG] query_embedding[:5]={query_embedding[:5]}")

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
          {filter_clause}
        ORDER BY score DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.mappings().all()

    print(f"[RETRIEVAL DIAG] rows returned={len(rows)}")
    if rows:
        print(f"[RETRIEVAL DIAG] top score={float(rows[0]['score']):.4f} doc_id={rows[0]['document_id']}")
    else:
        # Run a diagnostic query WITHOUT filters to see if ANY chunks exist
        diag_sql = text("SELECT count(*), min(org_id::text), min(document_id::text) FROM chunks")
        diag_result = await db.execute(diag_sql)
        diag_row = diag_result.mappings().first()
        print(f"[RETRIEVAL DIAG] NO RESULTS — total chunks in DB={diag_row['count']} sample_org_id={diag_row['min']} sample_doc_id={diag_row['min_1']}")

        diag_sql2 = text("SELECT count(*) FROM documents WHERE kb_id = :kb_id AND org_id = :org_id")
        diag_result2 = await db.execute(diag_sql2, {"kb_id": params["kb_id"], "org_id": params["org_id"]})
        diag_row2 = diag_result2.mappings().first()
        print(f"[RETRIEVAL DIAG] documents matching kb_id+org_id={diag_row2['count']}")

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
