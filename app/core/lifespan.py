from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from redis.asyncio import Redis

from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.core.telemetry import setup_telemetry
from app.db.session import engine
from app.providers.client_pool import ClientPool
from app.providers.registry import ProviderRegistry

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # ── Startup ──────────────────────────────────────
    setup_logging()
    setup_telemetry()
    logger.info("starting", app=settings.APP_NAME, env=settings.APP_ENV)

    # Redis
    app.state.redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    await app.state.redis.ping()
    logger.info("redis_connected")

    # HTTP client pool (shared httpx clients per provider)
    app.state.client_pool = ClientPool()
    await app.state.client_pool.startup()
    logger.info("client_pool_ready")

    # Provider registry (loads all adapters, builds capability map)
    app.state.registry = ProviderRegistry(app.state.client_pool)
    app.state.registry.load_all()
    logger.info("provider_registry_loaded", providers=len(app.state.registry.providers))

    yield

    # ── Shutdown ─────────────────────────────────────
    logger.info("shutting_down")
    await app.state.client_pool.shutdown()
    await app.state.redis.aclose()
    await engine.dispose()
    logger.info("shutdown_complete")
