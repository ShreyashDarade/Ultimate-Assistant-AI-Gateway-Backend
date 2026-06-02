"""Usage analytics routes — token counts, costs, and budget status."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.v1.deps import get_current_user_id, get_usage_service, rate_limit
from app.services.usage_service import UsageService

router = APIRouter(prefix="/usage", tags=["usage"], dependencies=[Depends(rate_limit)])


class UsageSummaryItem(BaseModel):
    provider: str
    model: str
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    avg_latency_ms: float


class DailyUsageItem(BaseModel):
    date: str
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float


class BudgetStatus(BaseModel):
    monthly_budget_usd: float | None
    current_spend_usd: float
    remaining_usd: float | None
    usage_percent: float | None


@router.get("/summary", response_model=list[UsageSummaryItem])
async def usage_summary(
    period: Literal["day", "week", "month"] = "month",
    user_id: uuid.UUID = Depends(get_current_user_id),
    usage_service: UsageService = Depends(get_usage_service),
):
    """Aggregate token counts, costs, and latency per provider/model."""
    days = {"day": 1, "week": 7, "month": 30}[period]
    since = datetime.now(timezone.utc) - timedelta(days=days)
    return await usage_service.get_summary(user_id, since)


@router.get("/daily", response_model=list[DailyUsageItem])
async def daily_usage(
    days: int = 30,
    user_id: uuid.UUID = Depends(get_current_user_id),
    usage_service: UsageService = Depends(get_usage_service),
):
    """Daily breakdown of usage for the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    return await usage_service.get_daily_breakdown(user_id, since)


@router.get("/budget", response_model=BudgetStatus)
async def budget_status(
    user_id: uuid.UUID = Depends(get_current_user_id),
    usage_service: UsageService = Depends(get_usage_service),
):
    """Current budget status — spend vs. monthly limit."""
    return await usage_service.get_budget_status(user_id)
