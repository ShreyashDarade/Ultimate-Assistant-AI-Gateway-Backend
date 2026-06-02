import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Usage(Base, TimestampMixin):
    __tablename__ = "usage"

    __table_args__ = (
        Index("ix_usage_user_created", "user_id", "created_at"),
        Index("ix_usage_provider_model", "provider", "model"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 8), default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
