from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.models.document import Document


async def create_document_record(
    db: AsyncSession,
    document_id: str,
    kb_id: str,
    filename: str,
    filepath: str,
) -> Document:
    """
    Insert a new document row with status=PENDING.
    Called by the upload route immediately after saving the file.
    """
    doc = Document(
        id=document_id,
        kb_id=kb_id,
        filename=filename,
        file_path=filepath,
        status="pending"
    )
    db.add(doc)
    await db.flush()  # write to DB within this transaction, but don't commit yet
    # commit happens automatically in get_db() after the route returns

    return doc


async def get_document_by_id(db: AsyncSession, document_id: str) -> Document:
    """
    Fetch a document record by ID.
    Raises 404 if not found.
    """
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Document '{document_id}' not found.",
        )
    return doc


async def update_document_status(
    db: AsyncSession,
    document_id: str,
    status: str,
    error_msg: str | None = None,
) -> Document:
    """
    Update document status. Called by the worker in later slices.
    Valid transitions: PENDING → PROCESSING → COMPLETED | FAILED
    """
    doc = await get_document_by_id(db, document_id)
    doc.status = status
    if error_msg:
        doc.error_msg = error_msg
    await db.flush()
    return doc
