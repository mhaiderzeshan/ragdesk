from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.api.deps import get_current_user
from app.schemas.auth import UserContext
from sqlalchemy import select
from app.models.knowledgebase import KnowledgeBase
from app.schemas.document import UploadResponse, DocumentStatusResponse
from app.services.storage import save_upload
from app.services.document import create_document_record, get_document_by_id
from app.db import get_db

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=202,
    summary="Upload a document for processing",
)

async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    # Fetch default KB for the org
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.org_id == current_user.org_id))
    kb = result.scalars().first()
    
    if not kb:
        raise HTTPException(status_code=400, detail="No Knowledge Base found for the organization.")
    kb_id = kb.id

    # 1. Save file to disk (validates extension + size)
    document_id, file_path = save_upload(file)

    # 2. Create DB record with status=PENDING
    await create_document_record(
        db=db,
        document_id=document_id,
        org_id=current_user.org_id,
        kb_id=kb_id,
        filename=file.filename,
        file_path=file_path,
    )

    # Ensure document record is persisted before attempting Celery enqueue
    await db.commit()

    try:
        from app.workers.tasks import process_document
        process_document.delay(document_id, file_path, kb_id)
    except Exception as e:
        # If Redis is unreachable or enqueue fails, mark doc as FAILED and save
        from app.services.document import update_document_status
        await update_document_status(db, document_id, "failed", f"Enqueue error: {str(e)}")
        await db.commit()
        
        raise HTTPException(
            status_code=503,
            detail=f"Failed to enqueue document for processing. Service unavailable. Error: {str(e)}"
        )
    return UploadResponse(
        document_id=document_id,
        filename=file.filename,
        status="PENDING",
        message="File received. Processing will begin shortly.",
    )


@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
    summary="Poll the processing status of a document",
)
async def get_document_status(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    The client calls this endpoint to check if processing is done.
    Returns status: PENDING | PROCESSING | COMPLETED | FAILED
    """
    doc = await get_document_by_id(db, document_id)
    return DocumentStatusResponse.model_validate(doc)
