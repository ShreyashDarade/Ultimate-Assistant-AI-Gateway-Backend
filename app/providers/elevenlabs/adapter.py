"""ElevenLabs adapter — high-quality TTS and STT."""

from app.providers.base import BaseProvider, STTCapable, TTSCapable
from app.providers.capabilities import Modality, ModalityPair
from app.providers.retry import with_retry
from app.schemas.provider import MediaResult, ModelInfo, UnifiedRequest, UnifiedResponse


class ElevenLabsAdapter(BaseProvider, TTSCapable, STTCapable):
    name = "elevenlabs"
    base_url = "https://api.elevenlabs.io"

    def _headers(self, api_key: str) -> dict:
        return {"xi-api-key": api_key, "Content-Type": "application/json"}

    def get_capabilities(self) -> dict[ModalityPair, list[str]]:
        return {
            (Modality.TEXT, Modality.AUDIO): ["eleven_multilingual_v2", "eleven_turbo_v2_5", "eleven_flash_v2_5"],
            (Modality.AUDIO, Modality.TEXT): ["scribe_v1"],
        }

    def get_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="eleven_multilingual_v2", name="Multilingual V2", provider="elevenlabs", modalities=["text→audio"], context_window=None, max_output_tokens=None),
            ModelInfo(id="eleven_turbo_v2_5", name="Turbo V2.5", provider="elevenlabs", modalities=["text→audio"], context_window=None, max_output_tokens=None),
            ModelInfo(id="eleven_flash_v2_5", name="Flash V2.5", provider="elevenlabs", modalities=["text→audio"], context_window=None, max_output_tokens=None),
            ModelInfo(id="scribe_v1", name="Scribe V1 (STT)", provider="elevenlabs", modalities=["audio→text"], context_window=None, max_output_tokens=None),
        ]

    @with_retry()
    async def text_to_speech(self, req: UnifiedRequest, api_key: str) -> MediaResult:
        voice_id = req.options.get("voice_id", "21m00Tcm4TlvDq8ikWAM") if req.options else "21m00Tcm4TlvDq8ikWAM"
        model_id = req.model or "eleven_turbo_v2_5"
        payload = {
            "text": req.prompt,
            "model_id": model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }
        resp = await self.client.post(
            f"/v1/text-to-speech/{voice_id}",
            json=payload,
            headers=self._headers(api_key),
        )
        resp.raise_for_status()
        # Returns raw audio bytes — caller uploads to S3
        return MediaResult(
            file_url="",  # set after S3 upload
            mime_type="audio/mpeg",
            model=model_id,
            provider="elevenlabs",
        )

    @with_retry()
    async def speech_to_text(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse:
        headers = {"xi-api-key": api_key}
        files = {"file": ("audio.webm", req.input_data, "audio/webm")}
        data = {"model_id": req.model or "scribe_v1"}
        resp = await self.client.post("/v1/speech-to-text", data=data, files=files, headers=headers)
        resp.raise_for_status()
        result = resp.json()
        return UnifiedResponse(
            content=result.get("text", ""),
            model=data["model_id"],
            provider="elevenlabs",
        )
