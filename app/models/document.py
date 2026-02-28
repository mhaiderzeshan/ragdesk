from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))

    # Relationship to Chunks
    chunks = relationship("Chunk", back_populates="document")
