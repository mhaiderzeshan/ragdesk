from datetime import datetime
from typing import Optional, Union
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    message: str


class DocumentStatusResponse(BaseModel):
    document_id: Union[str, UUID] = Field(validation_alias="id")
    kb_id: Union[str, UUID]
    filename: str
    status: str
    error_msg: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

