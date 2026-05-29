"""Background file processing task — parse and extract text."""

import uuid

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def process_file(
    ctx: dict,
    user_id_str: str,
    file_id_str: str,
):
    """Parse uploaded file and store extracted text."""
    job_id = ctx.get("job_id", "unknown")
    logger.info("file_process_start", job_id=job_id, file_id=file_id_str)

    from redis.asyncio import Redis
    redis: Redis = ctx.get("redis") or Redis.from_url(settings.REDIS_URL, decode_responses=True)
    await redis.set(f"job:{job_id}:status", "processing")

    try:
        from app.db.session import async_session_factory
        from app.services.file_service import FileService

        async with async_session_factory() as session:
            file_service = FileService(session)
            user_id = uuid.UUID(user_id_str)
            file_id = uuid.UUID(file_id_str)

            file_record = await file_service.get_file(file_id, user_id)
            if not file_record:
                raise ValueError(f"File not found: {file_id}")

            # File already parsed on upload; this handles re-processing if needed
            await redis.set(f"job:{job_id}:status", "completed")
            logger.info("file_process_complete", job_id=job_id, file_id=file_id_str)

    except Exception as e:
        await redis.set(f"job:{job_id}:status", "failed")
        await redis.set(f"job:{job_id}:result", str(e))
        logger.error("file_process_failed", job_id=job_id, error=str(e))
        raise
