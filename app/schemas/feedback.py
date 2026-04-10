import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class FeedbackCreate(BaseModel):
    message_id: uuid.UUID = Field(..., description="The assistant message being rated")
    rating: int = Field(..., ge=-1, le=1, description="1 = thumbs up, -1 = thumbs down")
    note: Optional[str] = Field(None, max_length=2000)


class FeedbackResponse(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    rating: int
    note: Optional[str]

    model_config = ConfigDict(from_attributes=True)
