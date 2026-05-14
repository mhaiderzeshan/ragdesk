import re
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Guardrails: Prompt Injection Sanitization
# ---------------------------------------------------------------------------

INJECTION_PATTERNS = [
    r"</context>",           # closing context tag
    r"<context>",           # opening context tag
    r"\[INST\]",            # Llama-style instruction marker
    r"\[/INST\]",           # Llama-style instruction closer
    r"<<SYS>>",             # Mistral/Mixtral system prompt marker
    r"<\|",                 # generic special token start
    r"\|>",                 # generic special token end
    r"<\|end",              # eos token variants
    r"─+>",                 # arrow-like injection attempts
    r"(?i)ignore\s+(all\s+)?previous\s+instructions?",
    r"(?i)disregard\s+(all\s+)?previous",
]

# Compiled once at module load for performance
_COMPILED_PATTERNS = [(re.compile(p, re.IGNORECASE), "[REDACTED]") for p in INJECTION_PATTERNS]


def sanitize_user_message(message: str) -> str:
    """
    Remove potential prompt injection markers from user input.

    Uses redaction rather than stripping to preserve message structure
    and avoid creating more coherent injection artifacts.
    """
    for pattern, replacement in _COMPILED_PATTERNS:
        message = pattern.sub(replacement, message)
    return message.strip()


# Context sanitization — applied to retrieved chunks before prompt injection
CONTEXT_INJECTION_PATTERNS = [
    (r"(?i)</context>", "ENDOFCONTEXT"),
    (r"(?i)<context>", "[CONTEXT OPEN]"),
    (r"\[INST\]", "[INSTR]"),
    (r"\[/INST\]", "[INSTR CLOSE]"),
    (r"<<SYS>>", "[SYS]"),
    (r"(?i)ignore\s+(all\s+)?previous\s+instructions?", "[IGNORED]"),
    (r"(?i)disregard\s+(all\s+)?previous", "[IGNORED]"),
    (r"(?i)you are now[:\s]", "[BECOMING]"),
]
_COMPILED_CONTEXT_PATTERNS = [(re.compile(p), r) for p, r in CONTEXT_INJECTION_PATTERNS]


def sanitize_context(text: str) -> str:
    """
    Sanitize a retrieved chunk before injection into the prompt.

    Defense-in-depth: the system prompt tells the model to ignore instructions
    in the context block, but technical sanitization provides an additional layer.
    """
    for pattern, replacement in _COMPILED_CONTEXT_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


# ---------------------------------------------------------------------------
# Retrieval Filters
# ---------------------------------------------------------------------------

class PageRangeFilter(BaseModel):
    min_page: Optional[int] = Field(None, ge=1, description="Inclusive lower bound (1-indexed)")
    max_page: Optional[int] = Field(None, ge=1, description="Inclusive upper bound (1-indexed)")


class RetrievalFilters(BaseModel):
    page_range: Optional[PageRangeFilter] = Field(
        None, description="Filter chunks by page number range"
    )
    document_types: Optional[list[str]] = Field(
        None, description="Filter chunks by document type tag"
    )
    section_contains: Optional[str] = Field(
        None, description="Substring match on section_title in metadata"
    )


class Citation(BaseModel):
    """A single source chunk returned alongside an answer."""
    chunk_id: str
    document_id: str
    document_name: Optional[str] = None
    score: float


class ChatRequest(BaseModel):
    kb_id: uuid.UUID = Field(..., description="Knowledge base to search")
    chat_id: Optional[uuid.UUID] = Field(
        None, description="Existing chat ID to continue a conversation; omit to start a new one"
    )
    message: str = Field(..., min_length=1, max_length=4000, description="The user's question")
    top_k: int = Field(6, ge=1, le=20, description="Number of chunks to retrieve")
    filters: Optional[RetrievalFilters] = Field(
        None, description="Optional filters for retrieval"
    )

    @model_validator(mode="after")
    def sanitize_message(self) -> "ChatRequest":
        self.message = sanitize_user_message(self.message)
        return self


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
