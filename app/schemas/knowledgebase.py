import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class KBCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class KBResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
