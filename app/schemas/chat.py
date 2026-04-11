import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    """A single source chunk returned alongside an answer."""
    chunk_id: str
    document_id: str
    score: float


class ChatRequest(BaseModel):
    kb_id: uuid.UUID = Field(..., description="Knowledge base to search")
    chat_id: Optional[uuid.UUID] = Field(
        None, description="Existing chat ID to continue a conversation; omit to start a new one"
    )
    message: str = Field(..., min_length=1, description="The user's question")
    top_k: int = Field(6, ge=1, le=20, description="Number of chunks to retrieve")


class ChatResponse(BaseModel):
    chat_id: uuid.UUID
    message_id: uuid.UUID
    answer: str
    citations: list[Citation]


# History

class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    retrieved_chunk_ids: list
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatHistoryResponse(BaseModel):
    chat_id: uuid.UUID = Field(validation_alias="id")
    kb_id: uuid.UUID
    created_at: datetime
    messages: list[MessageOut]

    model_config = ConfigDict(from_attributes=True)
