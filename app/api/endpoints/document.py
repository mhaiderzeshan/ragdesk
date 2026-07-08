from fastapi import APIRouter, File, Form, UploadFile, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.api.deps import get_current_user
from app.schemas.auth import UserContext
from app.models.knowledgebase import KnowledgeBase
from app.models.document import Document
from app.schemas.document import UploadResponse, DocumentStatusResponse
from app.services.storage import save_upload, delete_object
from app.services.document import create_document_record, get_document_by_id, update_document_status
from app.db import get_db
from app.core.rate_limit import limiter
from app.services.audit import log_action
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


def _get_org_kb(db: AsyncSession, org_id: uuid.UUID):
    """Helper: single-arg factory so we can avoid code duplication."""
    return select(KnowledgeBase).where(KnowledgeBase.org_id == org_id)


# Upload
@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=202,
    summary="Upload a document for processing",
)
@limiter.limit("10/minute")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    kb_id: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    kb_query = select(KnowledgeBase).where(KnowledgeBase.org_id == current_user.org_id)
    if kb_id:
        kb_query = kb_query.where(KnowledgeBase.id == kb_id)

    result = await db.execute(kb_query)
    kb = result.scalars().first()
    if not kb:
        detail = "Knowledge Base not found." if kb_id else "No Knowledge Base found for the organization."
        raise HTTPException(status_code=400, detail=detail)
    selected_kb_id = kb.id

    # 1. Save file to disk (validates extension + size)
    document_id, file_path = save_upload(file)

    # 2. Create DB record with status=PENDING
    await create_document_record(
        db=db,
        document_id=document_id,
        org_id=current_user.org_id,
        kb_id=selected_kb_id,
        filename=file.filename,
        file_path=file_path,
    )

    # Ensure document record is persisted before Celery enqueue
    await db.commit()
    
    # Audit logging
    await log_action(db, current_user.org_id, current_user.user_id, "upload_document", str(document_id))

    try:
        from app.workers.tasks import process_document
        # Pass org_id so the worker can scope chunk inserts correctly
        process_document.delay(
            document_id,
            file_path,
            str(selected_kb_id),
            str(current_user.org_id),
        )
    except Exception as e:
        # Enqueue failed — the file is already in R2 but will never be
        # processed. Clean up the orphaned object and mark the doc FAILED so
        # storage doesn't leak.
        if not delete_object(file_path):
            logger.warning("Could not delete orphaned R2 object %s", file_path)
        await update_document_status(db, document_id, "failed", f"Enqueue error: {str(e)}")
        await db.commit()
        raise HTTPException(
            status_code=503,
            detail=f"Failed to enqueue document for processing: {str(e)}",
        )

    return UploadResponse(
        document_id=document_id,
        filename=file.filename,
        status="PENDING",
        message="File received. Processing will begin shortly.",
    )


# List documents
@router.get(
    "",
    response_model=list[DocumentStatusResponse],
    summary="List all documents for this organisation",
)
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    result = await db.execute(
        select(Document).where(Document.org_id == current_user.org_id)
    )
    return result.scalars().all()


# Status poll
@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
    summary="Poll the processing status of a document",
)
async def get_document_status(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    doc = await get_document_by_id(db, document_id)
    # Enforce org scoping — 404 is safer than 403 to avoid enumeration
    if str(doc.org_id) != str(current_user.org_id):
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentStatusResponse.model_validate(doc)


# Reindex
@router.post(
    "/{document_id}/reindex",
    response_model=UploadResponse,
    status_code=202,
    summary="Re-chunk and re-embed a document (e.g. after config changes)",
)
@limiter.limit("5/minute")
async def reindex_document(
    request: Request,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    doc = await get_document_by_id(db, document_id)

    if str(doc.org_id) != str(current_user.org_id):
        raise HTTPException(status_code=404, detail="Document not found.")

    if not doc.file_path:
        raise HTTPException(status_code=400, detail="Document has no associated file to reindex.")

    # Reset status to PENDING and re-queue
    await update_document_status(db, document_id, "pending")
    await db.commit()

    # Audit logging
    await log_action(db, current_user.org_id, current_user.user_id, "reindex_document", str(document_id))

    try:
        from app.workers.tasks import process_document
        # The worker deletes old chunks before inserting new ones (idempotent)
        process_document.delay(
            document_id,
            doc.file_path,
            str(doc.kb_id),
            str(current_user.org_id),
        )
    except Exception as e:
        # Note: we do NOT delete the R2 object here — the file belongs to an
        # existing document and may be retried later. Only mark status FAILED.
        await update_document_status(db, document_id, "failed", f"Reindex enqueue error: {str(e)}")
        await db.commit()
        raise HTTPException(status_code=503, detail=f"Failed to enqueue reindex: {str(e)}")

    return UploadResponse(
        document_id=document_id,
        filename=doc.filename or "",
        status="PENDING",
        message="Reindex job queued. Old chunks will be replaced on completion.",
    )
