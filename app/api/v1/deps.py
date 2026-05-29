"""FastAPI dependencies — auth, DB session, services."""

import uuid
from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.ratelimit import TokenBucketLimiter
from app.core.security import decode_token
from app.db.repositories.conversation_repo import ConversationRepository
from app.db.repositories.key_repo import KeyRepository
from app.db.repositories.user_repo import UserRepository
from app.db.session import get_session
from app.providers.registry import ProviderRegistry
from app.services.cache import ResponseCache
from app.services.chat_service import ChatService
from app.services.conversion_service import ConversionService
from app.services.file_service import FileService
from app.services.key_service import KeyService
from app.services.pipeline import Pipeline
from app.services.router import ModalityRouter
from app.services.usage_service import UsageService

security = HTTPBearer()


async def get_db() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session


def get_redis(request: Request):
    return request.app.state.redis


def get_registry(request: Request) -> ProviderRegistry:
    return request.app.state.registry


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> uuid.UUID:
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise ValueError("Not an access token")
        return uuid.UUID(payload["sub"])
    except (ValueError, KeyError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def rate_limit(
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    redis = get_redis(request)
    limiter = TokenBucketLimiter(redis)
    await limiter.check(str(user_id))


# ── Repository deps ──────────────────────────────────

async def get_user_repo(session: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(session)


async def get_key_repo(session: AsyncSession = Depends(get_db)) -> KeyRepository:
    return KeyRepository(session)


async def get_conv_repo(session: AsyncSession = Depends(get_db)) -> ConversationRepository:
    return ConversationRepository(session)


# ── Service deps ─────────────────────────────────────

async def get_key_service(
    request: Request,
    key_repo: KeyRepository = Depends(get_key_repo),
) -> KeyService:
    redis = request.app.state.redis
    return KeyService(key_repo, redis)


async def get_router(
    request: Request,
    key_service: KeyService = Depends(get_key_service),
) -> ModalityRouter:
    registry = get_registry(request)
    return ModalityRouter(registry, key_service)


async def get_pipeline(
    router: ModalityRouter = Depends(get_router),
) -> Pipeline:
    return Pipeline(router)


async def get_chat_service(
    request: Request,
    router: ModalityRouter = Depends(get_router),
    key_service: KeyService = Depends(get_key_service),
    session: AsyncSession = Depends(get_db),
) -> ChatService:
    registry = get_registry(request)
    return ChatService(router, registry, key_service, session)


async def get_conversion_service(
    router: ModalityRouter = Depends(get_router),
    pipeline: Pipeline = Depends(get_pipeline),
) -> ConversionService:
    return ConversionService(router, pipeline)


async def get_file_service(
    session: AsyncSession = Depends(get_db),
) -> FileService:
    return FileService(session)


async def get_usage_service(
    session: AsyncSession = Depends(get_db),
) -> UsageService:
    return UsageService(session)


async def get_cache(request: Request) -> ResponseCache:
    redis = request.app.state.redis
    return ResponseCache(redis)
