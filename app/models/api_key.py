import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ApiKey(Base, TimestampMixin):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    encrypted_key: Mapped[str] = mapped_column(String(500), nullable=False)
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    is_valid: Mapped[bool] = mapped_column(default=True)

    user = relationship("User", back_populates="api_keys")
