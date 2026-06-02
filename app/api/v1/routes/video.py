"""Video routes — text→video and image→video generation (async via ARQ).

Video generation is asynchronous because it takes minutes.
The API returns a job ID immediately; the client polls for status.

Supports:
  - Text→video: Replicate (Kling), Fal (MiniMax)
  - Image→video: Upload an image + prompt to animate it
  - Job polling: GET /video/jobs/{job_id}
"""

import base64
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel, Field
from starlette import status

from app.api.v1.deps import get_current_user_id, rate_limit

router = APIRouter(prefix="/video", tags=["video"], dependencies=[Depends(rate_limit)])

# ── Limits ───────────────────────────────────────────

MAX_IMAGE_SIZE_MB = 20
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024

ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
}


# ── Schemas ──────────────────────────────────────────


class TextToVideoRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000, description="Text prompt for video generation")
    model: str | None = None
    provider: str | None = None
    duration: float = Field(5.0, ge=1.0, le=30.0, description="Video duration in seconds (1-30)")
    aspect_ratio: str = Field("16:9", pattern=r"^\d+:\d+$", description="Aspect ratio (e.g. 16:9, 9:16, 1:1)")
    options: dict | None = None


class ImageToVideoRequest(BaseModel):
    """Animate a still image into a video — provide image_url."""
    image_url: str = Field(..., description="URL of the source image")
    prompt: str = Field("Animate this image", max_length=4000)
    model: str | None = None
    provider: str | None = None
    duration: float = Field(5.0, ge=1.0, le=15.0, description="Video duration (1-15 seconds)")
    options: dict | None = None


class JobResponse(BaseModel):
    job_id: str
    status: str = "queued"
    message: str = "Generation queued. Poll GET /video/jobs/{job_id} for status."
    estimated_time_seconds: int | None = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str  # queued / processing / completed / failed
    result: str | None = None  # video URL when completed
    error: str | None = None
    progress: float | None = None  # 0.0 - 1.0


# ── Endpoints ────────────────────────────────────────


@router.post("/generate/text", response_model=JobResponse)
async def text_to_video(
    req: TextToVideoRequest,
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Generate a video from a text prompt (async).

    Returns a job_id immediately. Poll GET /video/jobs/{job_id} for status.
    Video generation typically takes 1-5 minutes depending on duration.
    Max duration: 30 seconds. Max prompt: 4000 chars.
    """
    from arq.connections import create_pool, RedisSettings
    from app.core.config import settings

    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    redis_pool = await create_pool(redis_settings)

    job = await redis_pool.enqueue_job(
        "generate_video",
        str(user_id),
        req.prompt,
        None,  # no image
        req.model,
        req.provider,
        {**(req.options or {}), "duration": req.duration, "aspect_ratio": req.aspect_ratio},
    )
    await redis_pool.aclose()

    return JobResponse(
        job_id=job.job_id,
        estimated_time_seconds=int(req.duration * 20),  # rough estimate
    )


@router.post("/generate/image-to-video", response_model=JobResponse)
async def image_to_video(
    req: ImageToVideoRequest,
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Animate a still image into a video (async, via URL).

    Provide a public image URL. Returns a job_id immediately.
    Supported image formats: PNG, JPEG, WebP.
    Max video duration: 15 seconds.
    """
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
        {**(req.options or {}), "duration": req.duration},
    )
    await redis_pool.aclose()

    return JobResponse(
        job_id=job.job_id,
        estimated_time_seconds=int(req.duration * 15),
    )


@router.post("/generate/image-to-video/upload", response_model=JobResponse)
async def image_to_video_upload(
    file: UploadFile = File(..., description="Source image to animate"),
    prompt: str = Form("Animate this image"),
    model: str | None = Form(None),
    provider: str | None = Form(None),
    duration: float = Form(5.0),
    request: Request = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Animate an uploaded image into a video (async, via file upload).

    Accepted formats: PNG, JPEG, WebP.
    Max image size: 20 MB. Max video duration: 15 seconds.
    """
    # Validate content type
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unsupported image format: {content_type}. Allowed: {', '.join(sorted(ALLOWED_IMAGE_TYPES))}",
        )

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Image exceeds max size of {MAX_IMAGE_SIZE_MB} MB",
        )

    if duration < 1.0 or duration > 15.0:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Duration must be between 1 and 15 seconds",
        )

    # Convert to data URI
    b64 = base64.b64encode(content).decode("utf-8")
    data_uri = f"data:{content_type};base64,{b64}"

    from arq.connections import create_pool, RedisSettings
    from app.core.config import settings

    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    redis_pool = await create_pool(redis_settings)

    job = await redis_pool.enqueue_job(
        "generate_video",
        str(user_id),
        prompt,
        data_uri,
        model,
        provider,
        {"duration": duration},
    )
    await redis_pool.aclose()

    return JobResponse(
        job_id=job.job_id,
        estimated_time_seconds=int(duration * 15),
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Poll job status for async video generation.

    Status values: queued → processing → completed / failed.
    When completed, the `result` field contains the video download URL.
    """
    redis = request.app.state.redis
    status_val = await redis.get(f"job:{job_id}:status")
    result = await redis.get(f"job:{job_id}:result")
    error = await redis.get(f"job:{job_id}:error")
    progress = await redis.get(f"job:{job_id}:progress")

    if not status_val:
        raise HTTPException(404, "Job not found or expired")

    return JobStatusResponse(
        job_id=job_id,
        status=status_val.decode() if isinstance(status_val, bytes) else str(status_val),
        result=result.decode() if isinstance(result, bytes) else result,
        error=error.decode() if isinstance(error, bytes) else error,
        progress=float(progress) if progress else None,
    )
