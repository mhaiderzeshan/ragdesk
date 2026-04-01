from fastapi import APIRouter, File, UploadFile, Depends
from sqlalchemy.ext.asyncio import AsyncSession

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
    kb_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    # 1. Save file to disk (validates extension + size)
    document_id, file_path = save_upload(file)

    # 2. Create DB record with status=PENDING
    await create_document_record(
        db=db,
        document_id=document_id,
        kb_id=kb_id,
        filename=file.filename,
        file_path=file_path,
    )

    # TODO (Slice 3): enqueue background task
    # process_document.delay(document_id, file_path, kb_id)

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
