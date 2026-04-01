from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    message: str


class DocumentStatusResponse(BaseModel):
    document_id: str
    kb_id: str
    filename: str
    status: str
    error_msg: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
