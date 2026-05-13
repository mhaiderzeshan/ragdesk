"""
Celery worker for document ingestion.
Pipeline: extract text → chunk → embed → store Chunk rows in Postgres/pgvector.
"""

import os
import re
import uuid
import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import List, Optional

from celery.exceptions import SoftTimeLimitExceeded
from app.workers.celery_app import celery_app
import pymupdf

import google.generativeai as genai
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.services.document import update_document_status

genai.configure(api_key=settings.GOOGLE_API_KEY.get_secret_value())

EMBEDDING_MODEL = "models/gemini-embedding-001"

# Chunk size and overlap for sentence-aware splitting
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

def _build_database_url() -> str:
    url = settings.DATABASE_URL
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


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


# ---------------------------------------------------------------------------
# Text Extraction and Structure-Aware Chunking
# ---------------------------------------------------------------------------

@dataclass
class ChunkWithMetadata:
    text: str
    page_number: int
    section_title: Optional[str]


def _split_into_sentences(text: str) -> List[str]:
    """
    Split text at sentence boundaries using a simple regex heuristic.
    Avoids splitting on common abbreviations (Dr., Mr., etc.).
    No external dependencies — uses regex only.
    """
    # Pattern: split on sentence-ending punctuation followed by whitespace.
    # Negative lookahead avoids splitting when punctuation is followed by
    # lowercase (e.g., "Dr. Smith" or "e.g. example").
    sentence_enders = re.compile(
        r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])$',
        re.MULTILINE
    )
    parts = sentence_enders.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def _merge_sentences_to_chunks(
    sentences: List[str],
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[str]:
    """
    Merge sentences into chunks that respect chunk_size limit.
    When a sentence exceeds chunk_size, split it at word boundaries.
    Overlap carries forward meaningful context between chunks.
    """
    if not sentences:
        return []

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for sentence in sentences:
        sent_len = len(sentence)

        # If single sentence exceeds chunk_size, split by words
        if sent_len > chunk_size:
            if current:
                chunks.append(" ".join(current))
                # Build overlap from end of current chunk
                overlap_text = " ".join(current)
                current = [overlap_text]
                current_len = len(overlap_text)
            words = sentence.split()
            sub_chunk: List[str] = []
            sub_len = 0
            for word in words:
                if sub_len + len(word) + 1 > chunk_size and sub_chunk:
                    chunks.append(" ".join(sub_chunk))
                    overlap_text = " ".join(sub_chunk)
                    sub_chunk = [overlap_text]
                    sub_len = len(overlap_text)
                sub_chunk.append(word)
                sub_len += len(word) + 1
            if sub_chunk:
                current = sub_chunk
                current_len = sub_len
        elif current_len + sent_len + len(current) > chunk_size:
            # Current chunk is full — emit and start new with overlap
            chunks.append(" ".join(current))
            overlap_text = " ".join(current[-2:])  # carry last 2 sentences
            current = [overlap_text, sentence]
            current_len = sum(len(s) for s in current)
        else:
            current.append(sentence)
            current_len += sent_len + (1 if len(current) > 1 else 0)

    if current:
        chunks.append(" ".join(current))

    return chunks


def _extract_page_heading(page: pymupdf.Page, toc: list, page_num: int) -> Optional[str]:
    """
    Try to find the nearest TOC/section heading for this page number.
    PyMuPDF TOC entries are [level, title, page_num (1-indexed)].
    Returns the title of the closest preceding heading.
    """
    if not toc:
        return None
    # TOC entries: [level, title, page]
    closest = None
    for entry in toc:
        if len(entry) >= 3 and entry[2] <= page_num:
            closest = entry[1]
        elif entry[2] > page_num:
            break
    return closest


def chunk_pdf_by_paragraphs(
    file_path: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[ChunkWithMetadata]:
    """
    Hybrid page-aware paragraph chunking using PyMuPDF blocks.

    Algorithm:
    1. Open PDF and build TOC (table of contents) for section headings.
    2. For each page, get text blocks with bounding boxes.
    3. Group blocks by vertical proximity to form paragraphs.
    4. Merge paragraph text, split at sentence boundaries, respect chunk_size.
    5. Track page_number and section_title (from TOC) per chunk.
    """
    doc = pymupdf.open(file_path)
    toc = doc.get_toc()  # [(level, title, page), ...]

    all_chunks: List[ChunkWithMetadata] = []

    for page_num, page in enumerate(doc, start=1):
        section_title = _extract_page_heading(page, toc, page_num)

        # Get text blocks with bounding boxes: (x0, y0, x1, y1, text, block_no, ...)
        blocks = page.get_text("blocks")
        if not blocks:
            continue

        # Sort blocks by vertical position (y0 top-to-bottom)
        blocks.sort(key=lambda b: (b[1], b[0]))  # sort by y0, then x0

        # Group blocks into paragraphs by vertical proximity (~12pt gap)
        # We track paragraphs as (paragraph_text, block_count)
        paragraphs: List[str] = []
        current_para: List[str] = []
        current_y0: Optional[float] = None
        PAGE_HEIGHT = page.rect.height

        for block in blocks:
            x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4]
            text = text.strip()
            if not text or len(text) < 3:
                continue

            # Skip very short blocks (likely page numbers, footers, headers)
            if len(text) < 20 and y0 < PAGE_HEIGHT * 0.1:
                continue
            if len(text) < 20 and y0 > PAGE_HEIGHT * 0.9:
                continue

            if current_y0 is None:
                current_y0 = y0
                current_para.append(text)
            elif abs(y0 - current_y0) < 12:  # same paragraph (within 12pt)
                # Check if block is roughly in same column (x0 proximity)
                if current_para:
                    current_para.append(text)
                    current_y0 = (current_y0 + y0) / 2
            else:
                # New paragraph
                if current_para:
                    paragraphs.append(" ".join(current_para))
                current_para = [text]
                current_y0 = y0

        if current_para:
            paragraphs.append(" ".join(current_para))

        # Process each paragraph into sentence-aware chunks
        for para in paragraphs:
            if len(para) < 30:  # skip very short paragraphs
                continue
            sentences = _split_into_sentences(para)
            if not sentences:
                continue
            text_chunks = _merge_sentences_to_chunks(sentences, chunk_size, overlap)
            for chunk_text in text_chunks:
                all_chunks.append(ChunkWithMetadata(
                    text=chunk_text,
                    page_number=page_num,
                    section_title=section_title,
                ))

    doc.close()
    return all_chunks


# Core async pipeline
async def _process_document_async(
    document_id: str,
    file_key: str,
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

            # 2. Extract text from file (Download from R2 first)
            import boto3
            import tempfile
            from botocore.exceptions import ClientError
            
            s3_client = boto3.client(
                "s3",
                endpoint_url=settings.R2_ENDPOINT_URL,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY.get_secret_value(),
                region_name="auto"
            )
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                temp_file_path = tmp_file.name
                
            try:
                try:
                    s3_client.download_file(
                        settings.R2_BUCKET_NAME,
                        file_key,
                        temp_file_path
                    )
                except ClientError as e:
                    raise FileNotFoundError(f"File not found in R2: {file_key}. Error: {str(e)}")

                doc_file = pymupdf.open(temp_file_path)
                full_text = "".join(page.get_text() for page in doc_file)
                doc_file.close()

                if not full_text.strip():
                    raise ValueError(
                        "Extracted text is empty. The document may be image-only or corrupt."
                    )

                # 3. Chunk text using structure-aware paragraph chunking
                pdf_chunks = chunk_pdf_by_paragraphs(temp_file_path, CHUNK_SIZE, CHUNK_OVERLAP)
                print(f"[{document_id}] Extracted {len(pdf_chunks)} chunks.")
            finally:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)

            if pdf_chunks:
                # 4. Generate embeddings (one per chunk)
                #    Add a small delay between calls to avoid 429 rate-limit
                #    errors on the free-tier Google AI API.
                embeddings: List[List[float]] = []
                for i, chunk_item in enumerate(pdf_chunks):
                    # Retry with exponential backoff on 429 / transient errors
                    max_retries = 5
                    for attempt in range(max_retries):
                        try:
                            response = genai.embed_content(
                                model=EMBEDDING_MODEL,
                                content=chunk_item.text,
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
                    if i < len(pdf_chunks) - 1:
                        time.sleep(1.0)

                # 5. Persist Chunk rows in Postgres (pgvector stores the vectors)
                #    Delete any existing chunks first (idempotency / reindex support)
                from sqlalchemy import delete as sql_delete
                from app.models.chunk import Chunk as ChunkModel

                await db.execute(
                    sql_delete(ChunkModel).where(ChunkModel.document_id == document_id)
                )

                for idx, (chunk_item, embedding) in enumerate(zip(pdf_chunks, embeddings)):
                    chunk = ChunkModel(
                        id=uuid.uuid4(),
                        org_id=org_id,
                        document_id=document_id,
                        chunk_index=idx,
                        text=chunk_item.text,
                        embedding=embedding,
                        metadata_jsonb={
                            "chunk_index": idx,
                            "page_number": chunk_item.page_number,
                            "section_title": chunk_item.section_title,
                        },
                    )
                    db.add(chunk)

                await db.flush()

            # 6. Update status → COMPLETED
            await update_document_status(db, document_id, "completed")
            await db.commit()
            print(
                f"[{document_id}] Successfully processed — {len(pdf_chunks)} chunks stored."
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
def process_document(self, document_id: str, file_key: str, kb_id: str, org_id: str):
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
                _process_document_async(document_id, file_key, kb_id, org_id)
            )
        finally:
            loop.close()

    except (ConnectionError, TimeoutError, SoftTimeLimitExceeded) as exc:
        raise self.retry(exc=exc, countdown=5 * (self.request.retries + 1))
    except Exception:
        # Status already updated to FAILED inside the async function
        pass
