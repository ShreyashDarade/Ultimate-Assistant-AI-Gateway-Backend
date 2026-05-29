import asyncio
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

import httpx

from app.core.exceptions import ProviderError, ProviderUnavailable
from app.core.logging import get_logger

# HTTP status codes worth retrying (transient / server-side / throttling).
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


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

logger = get_logger(__name__)


class CircuitBreaker:
    """Simple circuit breaker per provider."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failures: dict[str, int] = {}
        self._last_failure: dict[str, float] = {}
        self._open: dict[str, bool] = {}

    def is_open(self, provider: str) -> bool:
        if not self._open.get(provider, False):
            return False
        elapsed = time.monotonic() - self._last_failure.get(provider, 0)
        if elapsed > self.recovery_timeout:
            self._open[provider] = False
            self._failures[provider] = 0
            logger.info("circuit_closed", provider=provider)
            return False
        return True

    def record_success(self, provider: str) -> None:
        self._failures[provider] = 0
        self._open[provider] = False

    def record_failure(self, provider: str) -> None:
        self._failures[provider] = self._failures.get(provider, 0) + 1
        self._last_failure[provider] = time.monotonic()
        if self._failures[provider] >= self.failure_threshold:
            self._open[provider] = True
            logger.warning("circuit_opened", provider=provider, failures=self._failures[provider])


circuit_breaker = CircuitBreaker()


def with_retry(max_retries: int = 3, backoff_base: float = 0.5):
    """Decorator for retrying provider calls with exponential backoff."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            provider_name = getattr(args[0], "name", "unknown") if args else "unknown"

            if circuit_breaker.is_open(provider_name):
                raise ProviderUnavailable(provider_name)

            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    result = await func(*args, **kwargs)
                    circuit_breaker.record_success(provider_name)
                    return result
                except ProviderUnavailable:
                    raise
                except httpx.HTTPStatusError as e:
                    status_code = e.response.status_code
                    # Client errors (e.g. invalid key, bad request) are not
                    # transient — fail fast without consuming retries or
                    # tripping the circuit breaker.
                    if status_code not in RETRYABLE_STATUS:
                        raise ProviderError(
                            provider_name, _safe_error_body(e.response), status_code=status_code
                        ) from e
                    last_error = e
                    circuit_breaker.record_failure(provider_name)
                    if attempt < max_retries:
                        wait = backoff_base * (2 ** attempt)
                        logger.warning(
                            "provider_retry",
                            provider=provider_name,
                            attempt=attempt + 1,
                            wait=wait,
                            status=status_code,
                        )
                        await asyncio.sleep(wait)
                except Exception as e:
                    last_error = e
                    circuit_breaker.record_failure(provider_name)
                    if attempt < max_retries:
                        wait = backoff_base * (2 ** attempt)
                        logger.warning(
                            "provider_retry",
                            provider=provider_name,
                            attempt=attempt + 1,
                            wait=wait,
                            error=str(e),
                        )
                        await asyncio.sleep(wait)

            raise ProviderError(provider_name, str(last_error))

        return wrapper
    return decorator
