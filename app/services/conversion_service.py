"""Conversion service — handles any-to-any modality conversions."""

import uuid

from app.core.logging import get_logger
from app.schemas.conversion import ConversionRequest, ConversionResponse
from app.schemas.provider import MediaResult, UnifiedRequest, UnifiedResponse
from app.services.pipeline import Pipeline
from app.services.router import ModalityRouter
from app.utils.ids import generate_id

logger = get_logger(__name__)


class ConversionService:
    def __init__(self, router: ModalityRouter, pipeline: Pipeline):
        self.router = router
        self.pipeline = pipeline

    async def convert(self, req: ConversionRequest, user_id: uuid.UUID) -> ConversionResponse:
        unified_req = UnifiedRequest(
            prompt=req.input,
            model=req.model,
            options=req.options,
        )

        # Try direct route first, then pipeline
        try:
            result = await self.router.route(
                unified_req, user_id,
                req.input_modality, req.output_modality,
                preferred_provider=req.provider,
                preferred_model=req.model,
            )
        except Exception:
            # Fall back to pipeline for composite conversions
            result = await self.pipeline.execute(
                user_id, req.input,
                req.input_modality, req.output_modality,
                preferred_provider=req.provider,
                options=req.options,
            )

        if isinstance(result, UnifiedResponse):
            return ConversionResponse(
                id=generate_id(),
                output=result.content or "",
                output_modality=req.output_modality,
                model=result.model or "",
                provider=result.provider or "",
                latency_ms=result.latency_ms,
            )
        elif isinstance(result, MediaResult):
            return ConversionResponse(
                id=generate_id(),
                output=result.file_url,
                output_modality=req.output_modality,
                model=result.model,
                provider=result.provider,
                latency_ms=result.latency_ms,
            )

        raise ValueError("Unexpected result type from routing")
