"""Provider ranker — scores and ranks providers by latency, error rate, and cost.

Used by the ModalityRouter to pick the best provider for each request and
to order the failover list.
"""

from redis.asyncio import Redis

from app.core.logging import get_logger
from app.utils.tokens import estimate_cost

logger = get_logger(__name__)

# Default cost weight when we have no pricing data.
_DEFAULT_COST_WEIGHT = 1.0


class ProviderRanker:
    """Rank (provider, model) candidates by a composite score.

    Score = p50_latency_ms × (1 + error_rate) × cost_weight

    Lower is better.  Stats are stored in Redis and updated by the router
    after every request.
    """

    def __init__(self, redis: Redis):
        self.redis = redis

    async def rank(
        self, candidates: list[tuple[str, str]]
    ) -> list[tuple[str, str]]:
        """Return *candidates* sorted best-first."""
        if len(candidates) <= 1:
            return candidates

        scored: list[tuple[float, str, str]] = []
        for provider, model in candidates:
            score = await self._score(provider, model)
            scored.append((score, provider, model))

        scored.sort(key=lambda x: x[0])
        return [(p, m) for _, p, m in scored]

    async def _score(self, provider: str, model: str) -> float:
        p50 = await self._get_float(f"stats:latency:p50:{provider}:{model}", 500.0)
        error_rate = await self._get_float(f"stats:errors:rate:{provider}", 0.0)
        # Use the cost of 1K input+output tokens as the weight.
        cost_weight = estimate_cost(provider, model, 1000, 1000) or _DEFAULT_COST_WEIGHT
        return p50 * (1.0 + error_rate) * cost_weight

    async def _get_float(self, key: str, default: float) -> float:
        val = await self.redis.get(key)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
        return default

    # ── Stats recording (called by the router after each request) ──

    async def record_success(
        self, provider: str, model: str, latency_ms: int
    ) -> None:
        """Record a successful request — updates rolling latency and error rate."""
        lat_key = f"stats:latency:p50:{provider}:{model}"
        err_key = f"stats:errors:rate:{provider}"
        success_key = f"stats:success:{provider}"
        failure_key = f"stats:failure:{provider}"

        # Exponential moving average for latency (α = 0.3)
        current = await self._get_float(lat_key, float(latency_ms))
        new_avg = current * 0.7 + latency_ms * 0.3
        pipe = self.redis.pipeline()
        pipe.setex(lat_key, 3600, str(round(new_avg, 1)))
        pipe.incr(success_key)
        pipe.expire(success_key, 3600)
        await pipe.execute()

        # Recompute error rate
        await self._update_error_rate(provider, err_key, success_key, failure_key)

    async def record_failure(self, provider: str, model: str) -> None:
        err_key = f"stats:errors:rate:{provider}"
        success_key = f"stats:success:{provider}"
        failure_key = f"stats:failure:{provider}"

        pipe = self.redis.pipeline()
        pipe.incr(failure_key)
        pipe.expire(failure_key, 3600)
        await pipe.execute()

        await self._update_error_rate(provider, err_key, success_key, failure_key)

    async def _update_error_rate(
        self, provider: str, err_key: str, success_key: str, failure_key: str
    ) -> None:
        pipe = self.redis.pipeline()
        pipe.get(success_key)
        pipe.get(failure_key)
        results = await pipe.execute()

        successes = int(results[0] or 0)
        failures = int(results[1] or 0)
        total = successes + failures
        rate = failures / total if total > 0 else 0.0
        await self.redis.setex(err_key, 3600, str(round(rate, 4)))
