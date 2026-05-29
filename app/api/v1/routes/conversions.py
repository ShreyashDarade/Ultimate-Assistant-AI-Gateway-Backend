"""Conversions route — generic any→any endpoint."""

import uuid

from fastapi import APIRouter, Depends

from app.api.v1.deps import get_conversion_service, get_current_user_id, rate_limit
from app.schemas.conversion import ConversionRequest, ConversionResponse
from app.services.conversion_service import ConversionService

router = APIRouter(prefix="/conversions", tags=["conversions"], dependencies=[Depends(rate_limit)])


@router.post("", response_model=ConversionResponse)
async def convert(
    req: ConversionRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: ConversionService = Depends(get_conversion_service),
):
    """Universal conversion: specify input/output modalities.

    Examples:
    - text→image: {"input": "a red fox", "output_modality": "image"}
    - text→audio: {"input": "Hello world", "output_modality": "audio"}
    - image→text: {"input": "<file_id>", "input_modality": "image", "output_modality": "text"}
    """
    return await service.convert(req, user_id)
