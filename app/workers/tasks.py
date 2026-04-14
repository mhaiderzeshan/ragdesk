"""
Celery worker for document ingestion.
Pipeline: extract text → chunk → embed → store Chunk rows in Postgres/pgvector.
"""

import os
import uuid
import asyncio
import time
from contextlib import asynccontextmanager
from typing import List

from celery.exceptions import SoftTimeLimitExceeded
from app.workers.celery_app import celery_app
import pymupdf

import google.generativeai as genai
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.services.document import update_document_status

genai.configure(api_key=settings.GOOGLE_API_KEY.get_secret_value())

EMBEDDING_MODEL = "models/gemini-embedding-001"


def _build_database_url() -> str:
    """Build the async database URL from settings (avoids importing the shared engine)."""
    return (
        f"postgresql+asyncpg://"
        f"{settings.DB_USER}:{settings.DB_PASSWORD.get_secret_value()}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    )


@asynccontextmanager
async def _worker_session():
    """
    Create a *fresh* async engine + session for each Celery task invocation.

    Celery uses a prefork model: the parent process imports app.db (creating
    a module-level async engine), then forks.  Child workers inherit the
    engine's connection pool, but asyncpg connections are *not* fork-safe,
    causing "got Future attached to a different loop" and
    "cannot perform operation: another operation is in progress" errors.

    By creating a new engine inside the task's own event loop, we guarantee
    a clean, fork-safe connection pool every time.
    """
    url = _build_database_url()
    engine = create_async_engine(url, echo=False, pool_size=2, max_overflow=0)
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    try:
        async with session_factory() as session:
            yield session
    finally:
        await engine.dispose()


# Text chunking
def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Simple length-based chunking with overlap."""
    if not text.strip():
        return []

    chunks: List[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunks.append(text[start:end])
        if end == text_len:
            break
        start += chunk_size - overlap

    return chunks


# Core async pipeline
async def _process_document_async(
    document_id: str,
    file_path: str,
    kb_id: str,
    org_id: str,
) -> None:
    """Full ingestion pipeline — runs inside the Celery worker's event loop."""
    from app.models.chunk import Chunk  # avoid circular import at module level

    async with _worker_session() as db:
        try:
            # 1. Mark as PROCESSING
            await update_document_status(db, document_id, "processing")
            await db.commit()

            # 2. Extract text from file
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            doc_file = pymupdf.open(file_path)
            full_text = "".join(page.get_text() for page in doc_file)
            doc_file.close()

            if not full_text.strip():
                raise ValueError(
                    "Extracted text is empty. The document may be image-only or corrupt."
                )

            # 3. Chunk text
            chunks = chunk_text(full_text)
            print(f"[{document_id}] Extracted {len(chunks)} chunks.")

            if chunks:
                # 4. Generate embeddings (one per chunk)
                #    Add a small delay between calls to avoid 429 rate-limit
                #    errors on the free-tier Google AI API.
                embeddings: List[List[float]] = []
                for i, chunk_text_item in enumerate(chunks):
                    # Retry with exponential backoff on 429 / transient errors
                    max_retries = 5
                    for attempt in range(max_retries):
                        try:
                            response = genai.embed_content(
                                model=EMBEDDING_MODEL,
                                content=chunk_text_item,
                                task_type="retrieval_document",
                                output_dimensionality=768,
                            )
                            embeddings.append(response["embedding"])
                            break
                        except Exception as embed_err:
                            if "429" in str(embed_err) and attempt < max_retries - 1:
                                wait = 2 ** (attempt + 1)  # 2, 4, 8, 16s
                                print(
                                    f"[{document_id}] 429 rate-limited on chunk {i}, retrying in {wait}s (attempt {attempt + 1}/{max_retries})"
                                )
                                time.sleep(wait)
                            else:
                                raise
                    # Throttle: pause between embedding calls to stay within quota
                    if i < len(chunks) - 1:
                        time.sleep(1.0)

                # 5. Persist Chunk rows in Postgres (pgvector stores the vectors)
                #    Delete any existing chunks first (idempotency / reindex support)
                from sqlalchemy import delete as sql_delete
                from app.models.chunk import Chunk as ChunkModel

                await db.execute(
                    sql_delete(ChunkModel).where(ChunkModel.document_id == document_id)
                )

                for idx, (text_chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    chunk = ChunkModel(
                        id=uuid.uuid4(),
                        org_id=org_id,
                        document_id=document_id,
                        chunk_index=idx,
                        text=text_chunk,
                        embedding=embedding,
                        metadata_jsonb={"chunk_index": idx},
                    )
                    db.add(chunk)

                await db.flush()

            # 6. Update status → COMPLETED
            await update_document_status(db, document_id, "completed")
            await db.commit()
            print(
                f"[{document_id}] Successfully processed — {len(chunks)} chunks stored."
            )

        except Exception as exc:
            error_msg = str(exc)
            print(f"[{document_id}] Failed: {error_msg}")
            try:
                await update_document_status(
                    db, document_id, "failed", error_msg=error_msg
                )
                await db.commit()
            except Exception as inner:
                print(f"[{document_id}] Could not update failure status: {inner}")
            raise


# Celery task


@celery_app.task(bind=True, max_retries=3, soft_time_limit=300)
def process_document(self, document_id: str, file_path: str, kb_id: str, org_id: str):
    """
    Celery task — runs the async ingestion pipeline synchronously.
    org_id is now required to scope chunk insertion to the correct tenant.
    """
    print(f"[Worker] Job received — document_id={document_id}")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                _process_document_async(document_id, file_path, kb_id, org_id)
            )
        finally:
            loop.close()

    except (ConnectionError, TimeoutError, SoftTimeLimitExceeded) as exc:
        raise self.retry(exc=exc, countdown=5 * (self.request.retries + 1))
    except Exception:
        # Status already updated to FAILED inside the async function
        pass
