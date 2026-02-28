from sqlalchemy import Integer, String, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from app.db import Base


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    doc_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id"), nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Remember
    # 1536 is the standard dimension for OpenAI embeddings.
    # If using local models (like Llama/Ollama), this might be 384 or 768.
    embedding: Mapped[Vector] = mapped_column(Vector(1536))

    metadata_info: Mapped[dict] = mapped_column(JSON, nullable=True)

    document = relationship(
        "Document", back_populates="chunks")
