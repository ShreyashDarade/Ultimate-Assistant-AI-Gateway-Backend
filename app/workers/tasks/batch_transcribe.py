"""Batch audio transcription task."""

import uuid

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def batch_transcribe(
    ctx: dict,
    user_id_str: str,
    file_ids: list[str],
    model: str | None = None,
    provider: str | None = None,
):
    """Transcribe multiple audio files in batch."""
    job_id = ctx.get("job_id", "unknown")
    logger.info("batch_transcribe_start", job_id=job_id, files=len(file_ids))

    from redis.asyncio import Redis
    redis: Redis = ctx.get("redis") or Redis.from_url(settings.REDIS_URL, decode_responses=True)
    await redis.set(f"job:{job_id}:status", "processing")

    results = []
    for file_id in file_ids:
        try:
            # TODO: Download file from S3, transcribe via provider
            results.append({"file_id": file_id, "status": "transcribed", "text": ""})
        except Exception as e:
            results.append({"file_id": file_id, "status": "failed", "error": str(e)})
            logger.warning("transcribe_failed", file_id=file_id, error=str(e))

    import orjson
    await redis.set(f"job:{job_id}:status", "completed")
    await redis.set(f"job:{job_id}:result", orjson.dumps(results).decode())
    logger.info("batch_transcribe_complete", job_id=job_id, results=len(results))
