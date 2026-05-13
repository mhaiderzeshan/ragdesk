from enum import Enum
from sqlalchemy import String, ForeignKey, Enum as SQLEnum, DateTime, text
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base
from .chunk import Chunk
from .base_mixins import UUIDIDMixin, TimestampMixin
import uuid


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base, UUIDIDMixin, TimestampMixin):
    __tablename__ = "documents"

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(
        "orgs.id", ondelete="CASCADE"), nullable=False, index=True)
    kb_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(
        "kbs.id", ondelete="CASCADE"), nullable=False, index=True)

    source_type: Mapped[str] = mapped_column(String(50))  # e.g., 'file', 'url'
    status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus, values_callable=lambda x: [e.value for e in x]),
        default=DocumentStatus.PENDING
)

    filename: Mapped[str] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=True)
    error_msg: Mapped[str] = mapped_column(String(1024), nullable=True)
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan")
