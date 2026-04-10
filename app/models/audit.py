import uuid
from typing import Optional

from sqlalchemy import String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from .base_mixins import UUIDIDMixin, TimestampMixin


class AuditLog(Base, UUIDIDMixin, TimestampMixin):
    """
    Audit trail for important actions (uploads, reindexes, chats).
    Scoped by org_id for tenant isolation.
    """
    __tablename__ = "audit_logs"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Store arbitrary request/action context
    metadata_jsonb: Mapped[dict] = mapped_column(JSONB, server_default="{}")
