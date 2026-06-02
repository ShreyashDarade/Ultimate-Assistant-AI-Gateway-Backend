"""Image routes — text→image generation, image→text vision, with proper validation.

Supports:
  - Image generation from text prompts
  - Vision analysis via URL or file upload
  - Configurable file size limits and format validation
"""

import uuid
from io import BytesIO
import base64

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from starlette import status

from app.api.v1.deps import get_current_user_id, get_router, rate_limit
from app.schemas.provider import MediaResult, UnifiedRequest, UnifiedResponse
from app.services.router import ModalityRouter

router = APIRouter(prefix="/images", tags=["images"], dependencies=[Depends(rate_limit)])

# ── Limits ───────────────────────────────────────────

MAX_IMAGE_SIZE_MB = 20
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024  # 20 MB

ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "image/bmp",
    "image/tiff",
}


# ── Schemas ──────────────────────────────────────────


class ImageGenRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000, description="Text prompt for image generation")
    model: str | None = None
    provider: str | None = None
    size: str = Field("1024x1024", pattern=r"^\d+x\d+$", description="Image dimensions (e.g. 1024x1024)")
    quality: str = Field("standard", pattern=r"^(standard|hd)$")
    style: str = Field("vivid", pattern=r"^(vivid|natural)$")
    n: int = Field(1, ge=1, le=4, description="Number of images (1-4)")
    options: dict | None = None


class VisionRequest(BaseModel):
    """Analyze an image via URL — use /images/vision/upload for file uploads."""
    image_url: str = Field(..., description="Public URL of the image to analyze")
    prompt: str = Field("Describe this image in detail.", max_length=4000)
    model: str | None = None
    provider: str | None = None
    max_tokens: int | None = Field(None, ge=1, le=4096)


class VisionResponse(BaseModel):
    content: str
    model: str | None = None
    provider: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None


# ── Endpoints ────────────────────────────────────────


@router.post("/generate")
async def generate_image(
    req: ImageGenRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    router_svc: ModalityRouter = Depends(get_router),
):
    """Generate an image from a text prompt.

    Providers: OpenAI (gpt-image-1), Stability, Fal, Replicate.
    Max prompt length: 4000 chars. Sizes: 256x256, 512x512, 1024x1024, 1792x1024.
    """
    options = req.options or {}
    options.update({"size": req.size, "quality": req.quality, "style": req.style, "n": req.n})
    unified = UnifiedRequest(prompt=req.prompt, model=req.model, options=options)
    result = await router_svc.route(unified, user_id, "text", "image", req.provider, req.model)
    return result


@router.post("/vision", response_model=VisionResponse)
async def image_to_text(
    req: VisionRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    router_svc: ModalityRouter = Depends(get_router),
):
    """Analyze/describe an image from a URL.

    Providers: OpenAI (gpt-4o), Anthropic (Claude Sonnet), Google (Gemini), Ollama (LLaVA).
    Supports PNG, JPEG, GIF, WebP image URLs.
    """
    unified = UnifiedRequest(
        prompt=req.prompt,
        model=req.model,
        input_url=req.image_url,
        max_tokens=req.max_tokens,
    )
    result = await router_svc.route(unified, user_id, "image", "text", req.provider, req.model)
    return VisionResponse(
        content=result.content or "",
        model=result.model,
        provider=result.provider,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
    )


@router.post("/vision/upload", response_model=VisionResponse)
async def image_to_text_upload(
    file: UploadFile = File(..., description="Image file to analyze"),
    prompt: str = Form("Describe this image in detail."),
    model: str | None = Form(None),
    provider: str | None = Form(None),
    max_tokens: int | None = Form(None),
    user_id: uuid.UUID = Depends(get_current_user_id),
    router_svc: ModalityRouter = Depends(get_router),
):
    """Analyze/describe an uploaded image file.

    Accepted formats: PNG, JPEG, GIF, WebP, BMP, TIFF, SVG.
    Max file size: 20 MB.
    The image is converted to a base64 data URI for provider consumption.
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
            f"Image exceeds max size of {MAX_IMAGE_SIZE_MB} MB (received {len(content) / 1024 / 1024:.1f} MB)",
        )

    # Convert to base64 data URI for providers that support it
    b64 = base64.b64encode(content).decode("utf-8")
    data_uri = f"data:{content_type};base64,{b64}"

    unified = UnifiedRequest(
        prompt=prompt,
        model=model,
        input_url=data_uri,
        max_tokens=max_tokens,
    )
    result = await router_svc.route(unified, user_id, "image", "text", provider, model)
    return VisionResponse(
        content=result.content or "",
        model=result.model,
        provider=result.provider,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
    )
