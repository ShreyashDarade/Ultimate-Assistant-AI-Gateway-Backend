"""Audit log — records security-sensitive actions for compliance."""

import uuid

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # e.g. login, logout, key_added, key_deleted, password_changed, budget_exceeded
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
