"""Retry + circuit-breaker for provider calls.

The circuit breaker uses Redis for shared state across Gunicorn workers.
It supports three states: closed → open → half-open → closed.
"""

import asyncio
import random
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

import httpx
from redis.asyncio import Redis

from app.core.exceptions import ProviderError, ProviderUnavailable
from app.core.logging import get_logger

# HTTP status codes worth retrying (transient / server-side / throttling).
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}

logger = get_logger(__name__)


def _safe_error_body(response: httpx.Response) -> str:
    """Extract a short, safe error message from a provider response."""
    try:
        body = response.json()
        if isinstance(body, dict):
            err = body.get("error")
            if isinstance(err, dict):
                return str(err.get("message") or err)
            return str(err or body)
        return str(body)
    except Exception:
        return f"HTTP {response.status_code}"


class CircuitBreaker:
    """Redis-backed circuit breaker with half-open state.

    States:
      - CLOSED: requests flow normally.
      - OPEN: all requests fail-fast for `recovery_timeout` seconds.
      - HALF_OPEN: one probe request is allowed through. If it succeeds,
        the circuit closes; if it fails, it re-opens.
    """

    def __init__(
        self,
        redis: Redis | None = None,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ):
        self.redis = redis
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        # In-process fallback (used when Redis is not available).
        self._failures: dict[str, int] = {}
        self._last_failure: dict[str, float] = {}
        self._open: dict[str, bool] = {}

    # ── Public API ──────────────────────────────────

    async def is_open(self, provider: str) -> bool:
        if self.redis:
            return await self._redis_is_open(provider)
        return self._local_is_open(provider)

    async def record_success(self, provider: str) -> None:
        if self.redis:
            await self._redis_record_success(provider)
        else:
            self._local_record_success(provider)

    async def record_failure(self, provider: str) -> None:
        if self.redis:
            await self._redis_record_failure(provider)
        else:
            self._local_record_failure(provider)

    # ── Redis-backed implementation ─────────────────

    async def _redis_is_open(self, provider: str) -> bool:
        state = await self.redis.get(f"cb:state:{provider}")
        if state == "open":
            last_fail = await self.redis.get(f"cb:last_fail:{provider}")
            elapsed = time.time() - float(last_fail or 0)
            if elapsed > self.recovery_timeout:
                # Transition to half-open: allow one probe request.
                await self.redis.setex(
                    f"cb:state:{provider}", int(self.recovery_timeout), "half_open"
                )
                logger.info("circuit_half_open", provider=provider)
                return False  # allow the probe
            return True
        if state == "half_open":
            # Only one request at a time in half-open. Use a lock.
            acquired = await self.redis.set(
                f"cb:probe_lock:{provider}", "1", nx=True, ex=10
            )
            if acquired:
                return False  # this request is the probe
            return True  # another probe is already in flight
        return False  # closed

    async def _redis_record_success(self, provider: str) -> None:
        pipe = self.redis.pipeline()
        pipe.delete(f"cb:failures:{provider}")
        pipe.set(f"cb:state:{provider}", "closed")
        pipe.delete(f"cb:probe_lock:{provider}")
        await pipe.execute()
        logger.info("circuit_closed", provider=provider)

    async def _redis_record_failure(self, provider: str) -> None:
        failures = await self.redis.incr(f"cb:failures:{provider}")
        await self.redis.expire(f"cb:failures:{provider}", int(self.recovery_timeout * 3))
        await self.redis.set(f"cb:last_fail:{provider}", str(time.time()))
        await self.redis.delete(f"cb:probe_lock:{provider}")

        state = await self.redis.get(f"cb:state:{provider}")
        if state == "half_open":
            # Probe failed — re-open.
            await self.redis.setex(
                f"cb:state:{provider}", int(self.recovery_timeout * 2), "open"
            )
            logger.warning("circuit_reopened", provider=provider)
        elif failures >= self.failure_threshold:
            await self.redis.setex(
                f"cb:state:{provider}", int(self.recovery_timeout * 2), "open"
            )
            logger.warning("circuit_opened", provider=provider, failures=failures)

    # ── In-process fallback ─────────────────────────

    def _local_is_open(self, provider: str) -> bool:
        if not self._open.get(provider, False):
            return False
        elapsed = time.monotonic() - self._last_failure.get(provider, 0)
        if elapsed > self.recovery_timeout:
            self._open[provider] = False
            self._failures[provider] = 0
            logger.info("circuit_closed", provider=provider)
            return False
        return True

    def _local_record_success(self, provider: str) -> None:
        self._failures[provider] = 0
        self._open[provider] = False

    def _local_record_failure(self, provider: str) -> None:
        self._failures[provider] = self._failures.get(provider, 0) + 1
        self._last_failure[provider] = time.monotonic()
        if self._failures[provider] >= self.failure_threshold:
            self._open[provider] = True
            logger.warning(
                "circuit_opened",
                provider=provider,
                failures=self._failures[provider],
            )


# Global instance — starts with in-process state; lifespan can inject Redis.
circuit_breaker = CircuitBreaker()


def with_retry(max_retries: int = 3, backoff_base: float = 0.5):
    """Decorator for retrying provider calls with exponential backoff + jitter."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            provider_name = (
                getattr(args[0], "name", "unknown") if args else "unknown"
            )

            if await circuit_breaker.is_open(provider_name):
                raise ProviderUnavailable(provider_name)

            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    result = await func(*args, **kwargs)
                    await circuit_breaker.record_success(provider_name)
                    return result
                except ProviderUnavailable:
                    raise
                except httpx.HTTPStatusError as e:
                    status_code = e.response.status_code
                    # Client errors are not transient — fail fast.
                    if status_code not in RETRYABLE_STATUS:
                        raise ProviderError(
                            provider_name,
                            _safe_error_body(e.response),
                            status_code=status_code,
                        ) from e
                    last_error = e
                    await circuit_breaker.record_failure(provider_name)
                    if attempt < max_retries:
                        # Exponential backoff with jitter.
                        base_wait = backoff_base * (2**attempt)
                        jitter = random.uniform(0, base_wait * 0.5)
                        wait = base_wait + jitter
                        logger.warning(
                            "provider_retry",
                            provider=provider_name,
                            attempt=attempt + 1,
                            wait=round(wait, 2),
                            status=status_code,
                        )
                        await asyncio.sleep(wait)
                except Exception as e:
                    last_error = e
                    await circuit_breaker.record_failure(provider_name)
                    if attempt < max_retries:
                        base_wait = backoff_base * (2**attempt)
                        jitter = random.uniform(0, base_wait * 0.5)
                        wait = base_wait + jitter
                        logger.warning(
                            "provider_retry",
                            provider=provider_name,
                            attempt=attempt + 1,
                            wait=round(wait, 2),
                            error=str(e),
                        )
                        await asyncio.sleep(wait)

            raise ProviderError(provider_name, str(last_error))

        return wrapper

    return decorator
