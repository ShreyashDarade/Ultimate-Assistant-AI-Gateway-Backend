"""Embeddings route — text→vector."""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.v1.deps import get_current_user_id, get_router, rate_limit
from app.schemas.provider import UnifiedRequest
from app.services.router import ModalityRouter

router = APIRouter(prefix="/embeddings", tags=["embeddings"], dependencies=[Depends(rate_limit)])


class EmbeddingRequest(BaseModel):
    input: str
    model: str | None = None
    provider: str | None = None


@router.post("")
async def create_embedding(
    req: EmbeddingRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    router_svc: ModalityRouter = Depends(get_router),
):
    """Generate text embeddings via any embedding provider."""
    unified = UnifiedRequest(prompt=req.input, model=req.model)
    result = await router_svc.route(unified, user_id, "text", "vector", req.provider, req.model)
    return result
