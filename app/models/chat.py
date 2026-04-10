from __future__ import annotations
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from .base_mixins import UUIDIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.message import Message


class Chat(Base, UUIDIDMixin, TimestampMixin):
    """
    A single conversation session between a user and a knowledge base.
    Scoped by org_id for tenant isolation.
    """
    __tablename__ = "chats"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kb_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kbs.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    messages: Mapped[list["Message"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
