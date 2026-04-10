from __future__ import annotations
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from .base_mixins import UUIDIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.chat import Chat
    from app.models.feedback import Feedback


class Message(Base, UUIDIDMixin, TimestampMixin):
    """
    A single turn in a chat session.
    role: 'user' | 'assistant'
    retrieved_chunk_ids: JSON array of chunk UUIDs used to build the answer —
    stored so answers can be audited and replayed later.
    """
    __tablename__ = "messages"

    chat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)

    role: Mapped[str] = mapped_column(String(20), nullable=False)   # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Blueprint requirement: store chunk IDs for audit/replay
    retrieved_chunk_ids: Mapped[list] = mapped_column(
        JSONB, server_default="[]", nullable=False)

    # Relationships
    chat: Mapped["Chat"] = relationship(back_populates="messages")
    feedback: Mapped[list["Feedback"]] = relationship(
        back_populates="message", cascade="all, delete-orphan")
