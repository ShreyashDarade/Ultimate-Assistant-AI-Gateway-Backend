"""Async video generation task — runs in arq worker."""

import uuid

from arq import Retry
from redis.asyncio import Redis

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.db.repositories.key_repo import KeyRepository
from app.providers.client_pool import ClientPool
from app.providers.registry import ProviderRegistry
from app.schemas.provider import UnifiedRequest
from app.services.key_service import KeyService
from app.services.router import ModalityRouter

logger = get_logger(__name__)


async def generate_video(
    ctx: dict,
    user_id_str: str,
    prompt: str,
    image_url: str | None,
    model: str | None,
    provider: str | None,
    options: dict | None,
):
    """Long-running video generation — dispatched from API, runs in worker."""
    job_id = ctx.get("job_id", "unknown")
    redis: Redis = ctx.get("redis") or Redis.from_url(settings.REDIS_URL, decode_responses=True)

    await redis.set(f"job:{job_id}:status", "processing")
    logger.info("video_gen_start", job_id=job_id, user_id=user_id_str)

    try:
        user_id = uuid.UUID(user_id_str)

        # Setup provider infrastructure
        client_pool = ClientPool()
        await client_pool.startup()
        registry = ProviderRegistry(client_pool)
        registry.load_all()

        async with async_session_factory() as session:
            key_repo = KeyRepository(session)
            key_service = KeyService(key_repo, redis)
            router = ModalityRouter(registry, key_service)

            input_modality = "image" if image_url else "text"
            output_modality = "video"

            req = UnifiedRequest(
                prompt=prompt,
                model=model,
                input_url=image_url,
                options=options,
            )
            result = await router.route(
                req, user_id, input_modality, output_modality, provider, model,
            )

            await redis.set(f"job:{job_id}:status", "completed")
            await redis.set(f"job:{job_id}:result", result.file_url if hasattr(result, "file_url") else str(result))
            logger.info("video_gen_complete", job_id=job_id)

        await client_pool.shutdown()

    except Exception as e:
        await redis.set(f"job:{job_id}:status", "failed")
        await redis.set(f"job:{job_id}:result", str(e))
        logger.error("video_gen_failed", job_id=job_id, error=str(e))
        raise
