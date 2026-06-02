"""Cost service — estimation, budget checking, and pricing data."""

from decimal import Decimal

from app.core.logging import get_logger
from app.utils.tokens import PRICING

logger = get_logger(__name__)


class CostService:
    """Estimate API costs and check user budgets."""

    @staticmethod
    def estimate(
        provider: str, model: str, input_tokens: int, output_tokens: int
    ) -> Decimal:
        """Return estimated cost in USD for a given request."""
        rates = PRICING.get((provider, model), (1.0, 3.0))
        cost = (input_tokens * rates[0] + output_tokens * rates[1]) / 1_000_000
        return Decimal(str(round(cost, 8)))

    @staticmethod
    async def check_budget(
        user_monthly_budget: Decimal | None,
        current_spend: Decimal,
        estimated_cost: Decimal,
    ) -> dict:
        """Check if a request would exceed the user's monthly budget.

        Returns a dict with:
          - allowed: bool
          - remaining: Decimal
          - warning: str | None
        """
        if user_monthly_budget is None:
            return {"allowed": True, "remaining": None, "warning": None}

        remaining = user_monthly_budget - current_spend
        new_remaining = remaining - estimated_cost

        if new_remaining < 0:
            return {
                "allowed": False,
                "remaining": remaining,
                "warning": f"Request would exceed monthly budget (${user_monthly_budget}). Current spend: ${current_spend}",
            }

        if remaining / user_monthly_budget < Decimal("0.1"):
            return {
                "allowed": True,
                "remaining": remaining,
                "warning": f"Less than 10% of monthly budget remaining (${remaining} of ${user_monthly_budget})",
            }

        return {"allowed": True, "remaining": remaining, "warning": None}
