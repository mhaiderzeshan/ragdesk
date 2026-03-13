from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base
from .base_mixins import UUIDIDMixin, TimestampMixin


class Organization(Base, UUIDIDMixin, TimestampMixin):
    __tablename__ = "orgs"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
