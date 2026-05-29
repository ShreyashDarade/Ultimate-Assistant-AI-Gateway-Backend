"""Audio routes — TTS and STT."""

import uuid

from fastapi import APIRouter, Depends, UploadFile, File
from pydantic import BaseModel

from app.api.v1.deps import get_current_user_id, get_router, rate_limit
from app.schemas.provider import UnifiedRequest
from app.services.router import ModalityRouter

router = APIRouter(prefix="/audio", tags=["audio"], dependencies=[Depends(rate_limit)])


class TTSRequest(BaseModel):
    text: str
    model: str | None = None
    provider: str | None = None
    voice: str = "alloy"
    format: str = "mp3"


@router.post("/tts")
async def text_to_speech(
    req: TTSRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    router_svc: ModalityRouter = Depends(get_router),
):
    """Convert text to speech audio."""
    unified = UnifiedRequest(
        prompt=req.text,
        model=req.model,
        options={"voice": req.voice, "format": req.format},
    )
    result = await router_svc.route(unified, user_id, "text", "audio", req.provider, req.model)
    return result


@router.post("/stt")
async def speech_to_text(
    file: UploadFile = File(...),
    model: str | None = None,
    provider: str | None = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
    router_svc: ModalityRouter = Depends(get_router),
):
    """Transcribe audio to text."""
    content = await file.read()
    unified = UnifiedRequest(model=model, input_data=content)
    result = await router_svc.route(unified, user_id, "audio", "text", provider, model)
    return result
