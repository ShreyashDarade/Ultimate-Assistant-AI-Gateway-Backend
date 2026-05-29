"""Video routes — text→video, image→video (async job via arq)."""

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.api.v1.deps import get_current_user_id, rate_limit

router = APIRouter(prefix="/video", tags=["video"], dependencies=[Depends(rate_limit)])


class VideoGenRequest(BaseModel):
    prompt: str
    image_url: str | None = None  # for image→video
    model: str | None = None
    provider: str | None = None
    options: dict | None = None


class JobResponse(BaseModel):
    job_id: str
    status: str = "queued"
    message: str = "Video generation queued. Poll /video/jobs/{job_id} for status."


@router.post("/generate", response_model=JobResponse)
async def generate_video(
    req: VideoGenRequest,
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Queue video generation as async job — returns job ID immediately."""
    from arq.connections import create_pool, RedisSettings
    from app.core.config import settings

    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    redis_pool = await create_pool(redis_settings)

    job = await redis_pool.enqueue_job(
        "generate_video",
        str(user_id),
        req.prompt,
        req.image_url,
        req.model,
        req.provider,
        req.options,
    )
    await redis_pool.aclose()
    return JobResponse(job_id=job.job_id)


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Poll job status for async video generation."""
    redis = request.app.state.redis
    status = await redis.get(f"job:{job_id}:status")
    result = await redis.get(f"job:{job_id}:result")
    return {
        "job_id": job_id,
        "status": status or "unknown",
        "result": result,
    }
