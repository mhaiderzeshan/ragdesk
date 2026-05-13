import os
import uuid
import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile, HTTPException

from app.core.config import settings

ALLOWED_EXTENSIONS = {".pdf"}


def _get_extension(filename: str) -> str:
    """Extract and lowercase the file extension."""
    _, ext = os.path.splitext(filename)
    return ext.lower()


def _validate_file(file: UploadFile) -> str:
    """
    Validate extension.
    Returns the extension if valid, raises HTTPException if not.
    """
    ext = _get_extension(file.filename)

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"File type '{ext}' is not allowed. "
                f"Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
            ),
        )
    return ext


def save_upload(file: UploadFile) -> tuple[str, str]:
    """
    Save the uploaded file to Cloudflare R2 storage.

    Returns:
        (document_id, file_key) — the generated ID and the R2 object key.
    """
    ext = _validate_file(file)

    # Check file size before uploading
    file.file.seek(0, 2)
    file_size_bytes = file.file.tell()
    file.file.seek(0)
    
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024

    if file_size_bytes == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if file_size_bytes > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File size {file_size_bytes / 1024 / 1024:.1f}MB "
                f"exceeds the limit of {settings.MAX_FILE_SIZE_MB}MB."
            ),
        )

    # Generate a unique ID for this document
    document_id = str(uuid.uuid4())
    file_key = f"{document_id}{ext}"

    s3_client = boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY.get_secret_value(),
        region_name="auto"
    )

    try:
        s3_client.upload_fileobj(
            file.file, 
            settings.R2_BUCKET_NAME, 
            file_key,
            ExtraArgs={'ContentType': file.content_type or 'application/pdf'}
        )
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload to cloud storage: {str(e)}")

    return document_id, file_key
