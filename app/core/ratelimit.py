"""Tiered rate limiting — per-user, per-endpoint, with rate-limit headers.

Uses a token-bucket algorithm backed by Redis.
User tier determines the bucket size and refill rate.
"""

from fastapi import HTTPException, Request
from redis.asyncio import Redis
from starlette import status

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# (max_tokens, refill_per_second) per tier
TIER_LIMITS: dict[str, tuple[int, float]] = {
    "free": (30, 0.5),        # 30 req burst, 0.5 req/s refill ≈ 30/min
    "pro": (300, 5.0),        # 300 burst, 5 req/s ≈ 300/min
    "enterprise": (3000, 50.0),  # 3000 burst, 50 req/s ≈ 3000/min
}

# Per-endpoint overrides: path_prefix → (max_tokens, refill_per_second)
ENDPOINT_LIMITS: dict[str, tuple[int, float]] = {
    "/api/v1/chat": (20, 0.33),      # tighter for LLM calls
    "/api/v1/images": (10, 0.17),    # even tighter for image gen
    "/api/v1/models": (120, 2.0),    # relaxed for metadata
    "/api/v1/usage": (60, 1.0),
}


class TokenBucketLimiter:
    """Redis-backed token bucket rate limiter."""

    def __init__(self, redis: Redis):
        self.redis = redis

    async def check(
        self,
        identifier: str,
        tier: str = "free",
        endpoint: str | None = None,
    ) -> dict:
        """Check rate limit. Raises HTTP 429 if exceeded.

        Returns rate-limit metadata for response headers.
        """
        # Determine limits
        if endpoint and endpoint in ENDPOINT_LIMITS:
            max_tokens, refill_rate = ENDPOINT_LIMITS[endpoint]
        else:
            max_tokens, refill_rate = TIER_LIMITS.get(tier, TIER_LIMITS["free"])

        key = f"ratelimit:{identifier}"
        if endpoint:
            key = f"ratelimit:{identifier}:{endpoint}"

        # Lua script for atomic token bucket
        lua = """
        local key = KEYS[1]
        local max_tokens = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])

        local data = redis.call('hmget', key, 'tokens', 'last_refill')
        local tokens = tonumber(data[1])
        local last_refill = tonumber(data[2])

        if tokens == nil then
            tokens = max_tokens
            last_refill = now
        end

        local elapsed = now - last_refill
        tokens = math.min(max_tokens, tokens + elapsed * refill_rate)
        last_refill = now

        local allowed = 0
        if tokens >= 1 then
            tokens = tokens - 1
            allowed = 1
        end

        redis.call('hmset', key, 'tokens', tokens, 'last_refill', last_refill)
        redis.call('expire', key, 120)

        return {allowed, math.floor(tokens), math.floor(max_tokens)}
        """

        import time
        now = time.time()

        result = await self.redis.eval(lua, 1, key, max_tokens, refill_rate, now)
        allowed, remaining, limit = int(result[0]), int(result[1]), int(result[2])

        if not allowed:
            retry_after = int(1 / refill_rate) if refill_rate > 0 else 60
            logger.warning("rate_limited", identifier=identifier, tier=tier, endpoint=endpoint)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        return {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
        }
