"""OpenAI adapter — chat, image gen, vision, TTS, STT, embeddings."""

import json
from collections.abc import AsyncIterator

import httpx

from app.providers.base import (
    BaseProvider, ChatCapable, EmbedCapable, ImageGenCapable,
    STTCapable, TTSCapable, VisionCapable,
)
from app.providers.capabilities import Modality, ModalityPair
from app.providers.openai.mapping import (
    from_chat_response, from_stream_chunk, to_chat_request,
    to_embedding_request, to_image_request, to_stt_request,
    to_tts_request, to_vision_request,
)
from app.providers.retry import with_retry
from app.schemas.provider import Chunk, MediaResult, ModelInfo, UnifiedRequest, UnifiedResponse


class OpenAIAdapter(BaseProvider, ChatCapable, ImageGenCapable, VisionCapable, TTSCapable, STTCapable, EmbedCapable):
    name = "openai"
    base_url = "https://api.openai.com"

    def _headers(self, api_key: str) -> dict:
        return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def get_capabilities(self) -> dict[ModalityPair, list[str]]:
        return {
            (Modality.TEXT, Modality.TEXT): ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "o3", "o4-mini"],
            (Modality.TEXT, Modality.IMAGE): ["gpt-image-1"],
            (Modality.IMAGE, Modality.TEXT): ["gpt-4o", "gpt-4o-mini"],
            (Modality.TEXT, Modality.AUDIO): ["tts-1", "tts-1-hd"],
            (Modality.AUDIO, Modality.TEXT): ["whisper-1"],
            (Modality.TEXT, Modality.VECTOR): ["text-embedding-3-small", "text-embedding-3-large"],
        }

    def get_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="gpt-4o", name="GPT-4o", provider="openai", modalities=["text→text", "image→text"], context_window=128000, max_output_tokens=16384),
            ModelInfo(id="gpt-4o-mini", name="GPT-4o Mini", provider="openai", modalities=["text→text", "image→text"], context_window=128000, max_output_tokens=16384),
            ModelInfo(id="gpt-4.1", name="GPT-4.1", provider="openai", modalities=["text→text"], context_window=1047576, max_output_tokens=32768),
            ModelInfo(id="gpt-4.1-mini", name="GPT-4.1 Mini", provider="openai", modalities=["text→text"], context_window=1047576, max_output_tokens=32768),
            ModelInfo(id="gpt-4.1-nano", name="GPT-4.1 Nano", provider="openai", modalities=["text→text"], context_window=1047576, max_output_tokens=32768),
            ModelInfo(id="o3", name="o3", provider="openai", modalities=["text→text"], context_window=200000, max_output_tokens=100000),
            ModelInfo(id="o4-mini", name="o4 Mini", provider="openai", modalities=["text→text"], context_window=200000, max_output_tokens=100000),
            ModelInfo(id="gpt-image-1", name="GPT Image 1", provider="openai", modalities=["text→image"], context_window=None, max_output_tokens=None),
            ModelInfo(id="tts-1", name="TTS-1", provider="openai", modalities=["text→audio"], context_window=None, max_output_tokens=None),
            ModelInfo(id="tts-1-hd", name="TTS-1 HD", provider="openai", modalities=["text→audio"], context_window=None, max_output_tokens=None),
            ModelInfo(id="whisper-1", name="Whisper", provider="openai", modalities=["audio→text"], context_window=None, max_output_tokens=None),
            ModelInfo(id="text-embedding-3-small", name="Embedding 3 Small", provider="openai", modalities=["text→vector"], context_window=8191, max_output_tokens=None),
            ModelInfo(id="text-embedding-3-large", name="Embedding 3 Large", provider="openai", modalities=["text→vector"], context_window=8191, max_output_tokens=None),
        ]

    @with_retry()
    async def chat(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse:
        payload = to_chat_request(req)
        payload["stream"] = False
        resp = await self.client.post("/v1/chat/completions", json=payload, headers=self._headers(api_key))
        resp.raise_for_status()
        return from_chat_response(resp.json())

    async def stream_chat(self, req: UnifiedRequest, api_key: str) -> AsyncIterator[Chunk]:
        payload = to_chat_request(req)
        payload["stream"] = True
        async with self.client.stream(
            "POST", "/v1/chat/completions", json=payload, headers=self._headers(api_key)
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                chunk = from_stream_chunk(json.loads(data_str))
                if chunk:
                    yield chunk

    @with_retry()
    async def text_to_image(self, req: UnifiedRequest, api_key: str) -> MediaResult:
        payload = to_image_request(req)
        resp = await self.client.post("/v1/images/generations", json=payload, headers=self._headers(api_key))
        resp.raise_for_status()
        data = resp.json()
        return MediaResult(
            file_url=data["data"][0].get("url", ""),
            mime_type="image/png",
            model=payload["model"],
            provider="openai",
        )

    @with_retry()
    async def image_to_text(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse:
        payload = to_vision_request(req)
        resp = await self.client.post("/v1/chat/completions", json=payload, headers=self._headers(api_key))
        resp.raise_for_status()
        return from_chat_response(resp.json())

    @with_retry()
    async def text_to_speech(self, req: UnifiedRequest, api_key: str) -> MediaResult:
        payload = to_tts_request(req)
        resp = await self.client.post("/v1/audio/speech", json=payload, headers=self._headers(api_key))
        resp.raise_for_status()
        # Returns raw audio bytes — caller should upload to S3
        return MediaResult(
            file_url="",  # will be set after S3 upload
            mime_type="audio/mpeg",
            model=payload["model"],
            provider="openai",
        )

    @with_retry()
    async def speech_to_text(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse:
        headers = {"Authorization": f"Bearer {api_key}"}
        files = {"file": ("audio.webm", req.input_data, "audio/webm")}
        data = {"model": "whisper-1"}
        resp = await self.client.post("/v1/audio/transcriptions", data=data, files=files, headers=headers)
        resp.raise_for_status()
        result = resp.json()
        return UnifiedResponse(content=result["text"], model="whisper-1", provider="openai")

    @with_retry()
    async def embed(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse:
        payload = to_embedding_request(req)
        resp = await self.client.post("/v1/embeddings", json=payload, headers=self._headers(api_key))
        resp.raise_for_status()
        data = resp.json()
        embedding = data["data"][0]["embedding"]
        return UnifiedResponse(
            content=json.dumps(embedding),
            model=payload["model"],
            provider="openai",
            input_tokens=data.get("usage", {}).get("total_tokens"),
        )
