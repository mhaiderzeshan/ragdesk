from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db import Base


class KnowledgeBase(Base):
    __tablename__ = "kbs"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow)
