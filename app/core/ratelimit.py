import time

from redis.asyncio import Redis

from app.core.config import settings
from app.core.exceptions import RateLimitExceeded


class TokenBucketLimiter:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.max_requests = settings.RATE_LIMIT_REQUESTS
        self.window = settings.RATE_LIMIT_WINDOW_SECONDS

    async def check(self, key: str) -> None:
        now = time.time()
        pipe = self.redis.pipeline()
        bucket_key = f"ratelimit:{key}"

        pipe.zremrangebyscore(bucket_key, 0, now - self.window)
        pipe.zcard(bucket_key)
        pipe.zadd(bucket_key, {str(now): now})
        pipe.expire(bucket_key, self.window)

        results = await pipe.execute()
        request_count = results[1]

        if request_count >= self.max_requests:
            raise RateLimitExceeded()
