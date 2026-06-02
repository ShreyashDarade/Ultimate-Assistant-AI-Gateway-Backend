import uuid
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Role-based access control
    role: Mapped[str] = mapped_column(String(20), default="user")  # user / admin / api_only

    # Tier determines rate limits and feature access
    tier: Mapped[str] = mapped_column(String(20), default="free")  # free / pro / enterprise

    # Monthly spending budget (NULL = unlimited)
    monthly_budget_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    files = relationship("File", back_populates="user", cascade="all, delete-orphan")
