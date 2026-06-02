"""Audio routes — TTS (text→audio) and STT (audio→text) with validation.

Supports:
  - TTS: text→audio via OpenAI (tts-1, tts-1-hd), ElevenLabs
  - STT: audio→text via OpenAI (whisper-1), ElevenLabs
  - Configurable file size limits and format validation for STT
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from starlette import status

from app.api.v1.deps import get_current_user_id, get_router, rate_limit
from app.schemas.provider import UnifiedRequest
from app.services.router import ModalityRouter

router = APIRouter(prefix="/audio", tags=["audio"], dependencies=[Depends(rate_limit)])

# ── Limits ───────────────────────────────────────────

MAX_AUDIO_SIZE_MB = 25
MAX_AUDIO_SIZE_BYTES = MAX_AUDIO_SIZE_MB * 1024 * 1024  # 25 MB (OpenAI Whisper limit)

# STT accepted formats (Whisper supports all of these)
ALLOWED_AUDIO_TYPES = {
    "audio/mpeg",         # .mp3
    "audio/mp3",          # .mp3 (alternate)
    "audio/mp4",          # .mp4, .m4a
    "audio/x-m4a",        # .m4a
    "audio/wav",          # .wav
    "audio/x-wav",        # .wav (alternate)
    "audio/webm",         # .webm
    "audio/ogg",          # .ogg, .oga
    "audio/flac",         # .flac
    "audio/x-flac",       # .flac (alternate)
    "video/webm",         # .webm (browser recordings often use video/webm)
    "video/mp4",          # .mp4 video with audio track
    "application/octet-stream",  # fallback — validate by extension
}

# For extension-based fallback validation
ALLOWED_AUDIO_EXTENSIONS = {
    ".mp3", ".mp4", ".m4a", ".wav", ".webm", ".ogg", ".oga", ".flac", ".opus",
}

# TTS output formats
SUPPORTED_TTS_FORMATS = {"mp3", "opus", "aac", "flac", "wav", "pcm"}

# TTS voices
SUPPORTED_VOICES = {"alloy", "ash", "ballad", "coral", "echo", "fable", "onyx", "nova", "sage", "shimmer"}


# ── Schemas ──────────────────────────────────────────


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096, description="Text to convert to speech")
    model: str | None = Field(None, description="TTS model (e.g. tts-1, tts-1-hd)")
    provider: str | None = None
    voice: str = Field("alloy", description=f"Voice: {', '.join(sorted(SUPPORTED_VOICES))}")
    format: str = Field("mp3", description=f"Output format: {', '.join(sorted(SUPPORTED_TTS_FORMATS))}")
    speed: float = Field(1.0, ge=0.25, le=4.0, description="Playback speed (0.25-4.0)")


class TTSResponse(BaseModel):
    file_url: str
    mime_type: str
    model: str
    provider: str
    format: str
    latency_ms: int | None = None


class STTResponse(BaseModel):
    text: str
    model: str | None = None
    provider: str | None = None
    language: str | None = None
    duration_seconds: float | None = None
    input_tokens: int | None = None
    latency_ms: int | None = None


# ── Endpoints ────────────────────────────────────────


@router.post("/tts", response_model=TTSResponse)
async def text_to_speech(
    req: TTSRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    router_svc: ModalityRouter = Depends(get_router),
):
    """Convert text to speech audio.

    Max text length: 4096 characters.
    Voices: alloy, ash, ballad, coral, echo, fable, onyx, nova, sage, shimmer.
    Output formats: mp3, opus, aac, flac, wav, pcm.
    Speed: 0.25x to 4.0x.
    """
    if req.voice not in SUPPORTED_VOICES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unsupported voice: {req.voice}. Supported: {', '.join(sorted(SUPPORTED_VOICES))}",
        )
    if req.format not in SUPPORTED_TTS_FORMATS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unsupported format: {req.format}. Supported: {', '.join(sorted(SUPPORTED_TTS_FORMATS))}",
        )

    unified = UnifiedRequest(
        prompt=req.text,
        model=req.model,
        options={"voice": req.voice, "format": req.format, "speed": req.speed},
    )
    result = await router_svc.route(unified, user_id, "text", "audio", req.provider, req.model)

    mime_map = {
        "mp3": "audio/mpeg",
        "opus": "audio/opus",
        "aac": "audio/aac",
        "flac": "audio/flac",
        "wav": "audio/wav",
        "pcm": "audio/pcm",
    }

    return TTSResponse(
        file_url=result.file_url,
        mime_type=mime_map.get(req.format, "audio/mpeg"),
        model=result.model,
        provider=result.provider,
        format=req.format,
        latency_ms=result.latency_ms,
    )


@router.post("/stt", response_model=STTResponse)
async def speech_to_text(
    file: UploadFile = File(..., description="Audio file to transcribe"),
    model: str | None = Form(None, description="STT model (e.g. whisper-1)"),
    provider: str | None = Form(None),
    language: str | None = Form(None, description="ISO 639-1 language code (e.g. en, es, fr)"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    router_svc: ModalityRouter = Depends(get_router),
):
    """Transcribe audio to text.

    Accepted formats: MP3, MP4, M4A, WAV, WebM, OGG, FLAC, Opus.
    Max file size: 25 MB.
    Optionally specify language code for better accuracy.
    """
    # Validate content type
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if content_type not in ALLOWED_AUDIO_TYPES and ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unsupported audio format: {content_type} ({ext or 'no extension'}). "
            f"Accepted formats: MP3, MP4, M4A, WAV, WebM, OGG, FLAC, Opus.",
        )

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_AUDIO_SIZE_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Audio file exceeds max size of {MAX_AUDIO_SIZE_MB} MB "
            f"(received {len(content) / 1024 / 1024:.1f} MB)",
        )

    if len(content) == 0:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Audio file is empty.",
        )

    # Build request
    options = {}
    if language:
        options["language"] = language

    unified = UnifiedRequest(
        model=model,
        input_data=content,
        options=options if options else None,
    )
    result = await router_svc.route(unified, user_id, "audio", "text", provider, model)

    return STTResponse(
        text=result.content or "",
        model=result.model,
        provider=result.provider,
        language=language,
        input_tokens=result.input_tokens,
        latency_ms=result.latency_ms,
    )
