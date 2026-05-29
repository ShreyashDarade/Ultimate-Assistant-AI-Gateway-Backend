from fastapi import HTTPException, Request
from fastapi.responses import ORJSONResponse
from starlette import status

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppException(Exception):
    def __init__(self, message: str, status_code: int = 500, detail: str | None = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail or message
        super().__init__(message)


class ProviderError(AppException):
    def __init__(self, provider: str, message: str, status_code: int = 502):
        super().__init__(f"[{provider}] {message}", status_code)
        self.provider = provider


class ProviderKeyMissing(AppException):
    def __init__(self, provider: str):
        super().__init__(
            f"No API key configured for provider: {provider}",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class ProviderUnavailable(ProviderError):
    def __init__(self, provider: str):
        super().__init__(provider, "Provider is currently unavailable", 503)


class RateLimitExceeded(AppException):
    def __init__(self):
        super().__init__("Rate limit exceeded", status.HTTP_429_TOO_MANY_REQUESTS)


class NotFoundError(AppException):
    def __init__(self, resource: str, id: str):
        super().__init__(f"{resource} not found: {id}", status.HTTP_404_NOT_FOUND)


class AuthenticationError(AppException):
    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED)


class CapabilityNotSupported(AppException):
    def __init__(self, input_mod: str, output_mod: str):
        super().__init__(
            f"No provider supports conversion: {input_mod} → {output_mod}",
            status.HTTP_400_BAD_REQUEST,
        )


async def app_exception_handler(_request: Request, exc: AppException) -> ORJSONResponse:
    logger.warning("app_error", message=exc.message, status=exc.status_code)
    return ORJSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "detail": exc.detail},
    )


async def unhandled_exception_handler(_request: Request, exc: Exception) -> ORJSONResponse:
    logger.exception("unhandled_error", error=str(exc))
    return ORJSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )
