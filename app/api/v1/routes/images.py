"""Image routes — text→image, image→text (vision)."""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.v1.deps import get_current_user_id, get_router, rate_limit
from app.schemas.provider import MediaResult, UnifiedRequest, UnifiedResponse
from app.services.router import ModalityRouter

router = APIRouter(prefix="/images", tags=["images"], dependencies=[Depends(rate_limit)])


class ImageGenRequest(BaseModel):
    prompt: str
    model: str | None = None
    provider: str | None = None
    size: str = "1024x1024"
    options: dict | None = None


class VisionRequest(BaseModel):
    image_url: str
    prompt: str = "Describe this image in detail."
    model: str | None = None
    provider: str | None = None


@router.post("/generate")
async def generate_image(
    req: ImageGenRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    router_svc: ModalityRouter = Depends(get_router),
):
    """Generate an image from text."""
    options = req.options or {}
    options["size"] = req.size
    unified = UnifiedRequest(prompt=req.prompt, model=req.model, options=options)
    result = await router_svc.route(unified, user_id, "text", "image", req.provider, req.model)
    return result


@router.post("/vision")
async def image_to_text(
    req: VisionRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    router_svc: ModalityRouter = Depends(get_router),
):
    """Describe/analyze an image (vision)."""
    unified = UnifiedRequest(prompt=req.prompt, model=req.model, input_url=req.image_url)
    result = await router_svc.route(unified, user_id, "image", "text", req.provider, req.model)
    return result
