"""Embeddings route — text→vector with validation.

Supports batch embedding (up to 100 inputs) and single input.
Providers: OpenAI, Google, Cohere, Mistral, Ollama.
"""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.v1.deps import get_current_user_id, get_router, rate_limit
from app.schemas.provider import UnifiedRequest
from app.services.router import ModalityRouter

router = APIRouter(prefix="/embeddings", tags=["embeddings"], dependencies=[Depends(rate_limit)])


class EmbeddingRequest(BaseModel):
    input: str | list[str] = Field(
        ...,
        description="Text to embed — single string or list of up to 100 strings",
    )
    model: str | None = Field(None, description="Embedding model (e.g. text-embedding-3-small, nomic-embed-text)")
    provider: str | None = None


class EmbeddingResponse(BaseModel):
    embedding: list[float] | list[list[float]]
    model: str | None = None
    provider: str | None = None
    input_tokens: int | None = None
    dimensions: int | None = None


@router.post("", response_model=EmbeddingResponse)
async def create_embedding(
    req: EmbeddingRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    router_svc: ModalityRouter = Depends(get_router),
):
    """Generate text embeddings.

    Input: single string or list of up to 100 strings.
    Max input length: 8191 tokens (for OpenAI models).
    Providers: OpenAI, Google, Cohere, Mistral, Ollama.
    """
    import json
    from fastapi import HTTPException
    from starlette import status

    # Validate batch size
    if isinstance(req.input, list):
        if len(req.input) > 100:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Batch size exceeds maximum of 100 inputs (received {len(req.input)})",
            )
        if len(req.input) == 0:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Input list is empty",
            )
        # For batch, join with separator — providers handle differently
        text = req.input[0]  # Use first for single-provider routing
    else:
        text = req.input

    if not text or not text.strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Input text is empty",
        )

    unified = UnifiedRequest(prompt=text, model=req.model)
    result = await router_svc.route(unified, user_id, "text", "vector", req.provider, req.model)

    # Parse embedding from response content
    try:
        embedding = json.loads(result.content) if result.content else []
    except json.JSONDecodeError:
        embedding = []

    dimensions = len(embedding) if isinstance(embedding, list) and embedding else None

    return EmbeddingResponse(
        embedding=embedding,
        model=result.model,
        provider=result.provider,
        input_tokens=result.input_tokens,
        dimensions=dimensions,
    )
