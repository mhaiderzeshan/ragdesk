from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
import uuid
from .base_mixins import TimestampMixin, UUIDIDMixin
from app.db import Base


class KnowledgeBase(Base, UUIDIDMixin, TimestampMixin):
    __tablename__ = "kbs"

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
