"""Usage tracking — token/cost accounting per user/key with analytics."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import Usage
from app.models.user import User
from app.services.cost_service import CostService


class UsageService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record(
        self,
        user_id: uuid.UUID,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: Decimal = Decimal("0"),
        latency_ms: int = 0,
    ) -> Usage:
        estimated = CostService.estimate(provider, model, input_tokens, output_tokens)
        usage = Usage(
            user_id=user_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            estimated_cost_usd=estimated,
            latency_ms=latency_ms,
        )
        self.session.add(usage)
        await self.session.flush()
        return usage

    async def get_summary(self, user_id: uuid.UUID, since: datetime) -> list[dict]:
        """Aggregate usage by provider and model since a given date."""
        result = await self.session.execute(
            select(
                Usage.provider,
                Usage.model,
                func.count().label("total_requests"),
                func.sum(Usage.input_tokens).label("total_input_tokens"),
                func.sum(Usage.output_tokens).label("total_output_tokens"),
                func.sum(Usage.estimated_cost_usd).label("total_cost_usd"),
                func.avg(Usage.latency_ms).label("avg_latency_ms"),
            )
            .where(Usage.user_id == user_id, Usage.created_at >= since)
            .group_by(Usage.provider, Usage.model)
            .order_by(func.sum(Usage.estimated_cost_usd).desc())
        )
        return [
            {
                "provider": row.provider,
                "model": row.model,
                "total_requests": row.total_requests,
                "total_input_tokens": int(row.total_input_tokens or 0),
                "total_output_tokens": int(row.total_output_tokens or 0),
                "total_cost_usd": float(row.total_cost_usd or 0),
                "avg_latency_ms": float(row.avg_latency_ms or 0),
            }
            for row in result.all()
        ]

    async def get_daily_breakdown(self, user_id: uuid.UUID, since: datetime) -> list[dict]:
        """Daily breakdown of usage."""
        result = await self.session.execute(
            select(
                cast(Usage.created_at, Date).label("date"),
                func.count().label("total_requests"),
                func.sum(Usage.input_tokens).label("total_input_tokens"),
                func.sum(Usage.output_tokens).label("total_output_tokens"),
                func.sum(Usage.estimated_cost_usd).label("total_cost_usd"),
            )
            .where(Usage.user_id == user_id, Usage.created_at >= since)
            .group_by(cast(Usage.created_at, Date))
            .order_by(cast(Usage.created_at, Date))
        )
        return [
            {
                "date": str(row.date),
                "total_requests": row.total_requests,
                "total_input_tokens": int(row.total_input_tokens or 0),
                "total_output_tokens": int(row.total_output_tokens or 0),
                "total_cost_usd": float(row.total_cost_usd or 0),
            }
            for row in result.all()
        ]

    async def get_budget_status(self, user_id: uuid.UUID) -> dict:
        """Return current month's spend vs. budget."""
        # Get user's budget
        user = await self.session.get(User, user_id)
        budget = getattr(user, "monthly_budget_usd", None) if user else None

        # Get current month's spend
        month_start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        result = await self.session.execute(
            select(func.sum(Usage.estimated_cost_usd))
            .where(Usage.user_id == user_id, Usage.created_at >= month_start)
        )
        current_spend = float(result.scalar() or 0)

        remaining = float(budget) - current_spend if budget else None
        usage_pct = (current_spend / float(budget) * 100) if budget else None

        return {
            "monthly_budget_usd": float(budget) if budget else None,
            "current_spend_usd": round(current_spend, 6),
            "remaining_usd": round(remaining, 6) if remaining is not None else None,
            "usage_percent": round(usage_pct, 1) if usage_pct is not None else None,
        }
