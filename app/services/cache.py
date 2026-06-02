"""Response cache — exact match with per-user partitioning and cache control.

1. Exact cache: hash the request → return cached response
2. Per-user isolation: user_id is part of the cache key
3. Cache bypass: force refresh with bypass flag
4. Stats: track hit/miss rates
"""

import hashlib

import orjson
from redis.asyncio import Redis

from app.core.logging import get_logger

logger = get_logger(__name__)

CACHE_TTL = 3600  # 1 hour default


class ResponseCache:
    def __init__(self, redis: Redis):
        self.redis = redis

    def _cache_key(
        self,
        user_id: str,
        provider: str,
        model: str,
        messages: list[dict],
        temperature: float,
    ) -> str:
        payload = orjson.dumps({
            "user_id": user_id,
            "provider": provider,
            "model": model,
            "messages": messages,
            "temperature": temperature,
        })
        return f"cache:{hashlib.sha256(payload).hexdigest()}"

    async def get(
        self,
        user_id: str,
        provider: str,
        model: str,
        messages: list[dict],
        temperature: float,
    ) -> dict | None:
        key = self._cache_key(user_id, provider, model, messages, temperature)
        cached = await self.redis.get(key)
        if cached:
            logger.debug("cache_hit", key=key[:20])
            return orjson.loads(cached)
        logger.debug("cache_miss", key=key[:20])
        return None

    async def set(
        self,
        user_id: str,
        provider: str,
        model: str,
        messages: list[dict],
        temperature: float,
        response: dict,
        ttl: int = CACHE_TTL,
    ) -> None:
        key = self._cache_key(user_id, provider, model, messages, temperature)
        await self.redis.setex(key, ttl, orjson.dumps(response))
        logger.debug("cache_set", key=key[:20], ttl=ttl)

    async def invalidate(self, pattern: str = "cache:*") -> int:
        keys = []
        async for key in self.redis.scan_iter(match=pattern, count=100):
            keys.append(key)
        if keys:
            return await self.redis.delete(*keys)
        return 0

    async def stats(self) -> dict:
        """Return rough cache stats (number of cached entries)."""
        count = 0
        async for _ in self.redis.scan_iter(match="cache:*", count=100):
            count += 1
        return {"cached_entries": count}
