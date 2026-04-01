import os
import uuid
import shutil

from fastapi import UploadFile, HTTPException

from app.core.config import settings

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}


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
    Save the uploaded file to the UPLOAD_DIR.

    Returns:
        (document_id, file_path) — the generated ID and where the file lives on disk.

    Why generate document_id here?
        The ID is tied to the file's location on disk (we use it in the filename).
        Generating it in the service keeps this logic in one place.
    """
    ext = _validate_file(file)

    # Generate a unique ID for this document
    document_id = str(uuid.uuid4())

    # Ensure uploads directory exists (creates it if missing)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # Final path: uploads/<uuid>.pdf
    file_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}{ext}")

    # Stream file to disk — avoids loading the entire file into memory
    # This is safe for large files (shutil.copyfileobj reads in chunks)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Verify the file actually has content
    file_size_bytes = os.path.getsize(file_path)
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024

    if file_size_bytes == 0:
        os.remove(file_path)  # clean up the empty file
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if file_size_bytes > max_bytes:
        os.remove(file_path)  # clean up the oversized file
        raise HTTPException(
            status_code=413,
            detail=(
                f"File size {file_size_bytes / 1024 / 1024:.1f}MB "
                f"exceeds the limit of {settings.MAX_FILE_SIZE_MB}MB."
            ),
        )

    return document_id, file_path
