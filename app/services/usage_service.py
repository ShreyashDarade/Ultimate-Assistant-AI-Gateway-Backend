"""Usage tracking — token/cost accounting per user/key."""

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import Usage


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
        usage = Usage(
            user_id=user_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            latency_ms=latency_ms,
        )
        self.session.add(usage)
        await self.session.flush()
        return usage
