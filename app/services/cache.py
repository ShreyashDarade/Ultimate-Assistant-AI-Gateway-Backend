"""Response cache + semantic cache.

1. Exact cache: hash the request → return cached response
2. Semantic cache (future): embed the prompt, find near-duplicates
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

    def _cache_key(self, provider: str, model: str, messages: list[dict], temperature: float) -> str:
        payload = orjson.dumps({
            "provider": provider,
            "model": model,
            "messages": messages,
            "temperature": temperature,
        })
        return f"cache:{hashlib.sha256(payload).hexdigest()}"

    async def get(self, provider: str, model: str, messages: list[dict], temperature: float) -> dict | None:
        key = self._cache_key(provider, model, messages, temperature)
        cached = await self.redis.get(key)
        if cached:
            logger.debug("cache_hit", key=key)
            return orjson.loads(cached)
        return None

    async def set(
        self,
        provider: str,
        model: str,
        messages: list[dict],
        temperature: float,
        response: dict,
        ttl: int = CACHE_TTL,
    ) -> None:
        key = self._cache_key(provider, model, messages, temperature)
        await self.redis.setex(key, ttl, orjson.dumps(response))
        logger.debug("cache_set", key=key, ttl=ttl)

    async def invalidate(self, pattern: str = "cache:*") -> int:
        keys = []
        async for key in self.redis.scan_iter(match=pattern, count=100):
            keys.append(key)
        if keys:
            return await self.redis.delete(*keys)
        return 0
