from __future__ import annotations
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import Text, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base
if TYPE_CHECKING:
    from app.models.document import Document
from app.models.base_mixins import UUIDIDMixin, TimestampMixin
import uuid


class Chunk(Base, UUIDIDMixin, TimestampMixin):
    __tablename__ = "chunks"

    # Joins can be slow during high-concurrency vector searches.Choose denormalization here to keep the vector query as fast as possible.
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(
        "orgs.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(
        "documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(
        Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # We use JSONB for flexible metadata like page numbers
    metadata_jsonb: Mapped[dict] = mapped_column(JSONB, server_default="{}")

    # Vector dimension: 1536 is standard for OpenAI
    embedding: Mapped[list[float]] = mapped_column(
        Vector(1536), nullable=False)

    document: Mapped["Document"] = relationship(back_populates="chunks")
