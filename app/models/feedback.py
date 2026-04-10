from __future__ import annotations
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from .base_mixins import UUIDIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.message import Message


class Feedback(Base, UUIDIDMixin, TimestampMixin):
    """
    User feedback on an assistant message.
    rating: 1 = thumbs up, -1 = thumbs down (blueprint spec).
    note: optional free-text comment.
    """
    __tablename__ = "feedback"

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)

    rating: Mapped[int] = mapped_column(Integer, nullable=False)   # 1 or -1
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    message: Mapped["Message"] = relationship(back_populates="feedback")
