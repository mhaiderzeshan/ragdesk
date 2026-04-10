from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
import uuid
from app.db import Base
from .base_mixins import UUIDIDMixin, TimestampMixin


class User(Base, UUIDIDMixin, TimestampMixin):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # RBAC: "admin" can manage the org; "user" is a regular member
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="user")

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
