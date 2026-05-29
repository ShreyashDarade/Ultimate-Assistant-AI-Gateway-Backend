"""Groq adapter — ultra-fast chat inference + Whisper STT (OpenAI-compatible)."""

import json
from collections.abc import AsyncIterator

from app.providers.base import BaseProvider, ChatCapable, STTCapable
from app.providers.capabilities import Modality, ModalityPair
from app.providers.retry import with_retry
from app.schemas.provider import Chunk, ModelInfo, UnifiedRequest, UnifiedResponse


class GroqAdapter(BaseProvider, ChatCapable, STTCapable):
    name = "groq"
    base_url = "https://api.groq.com/openai"

    def _headers(self, api_key: str) -> dict:
        return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def get_capabilities(self) -> dict[ModalityPair, list[str]]:
        return {
            (Modality.TEXT, Modality.TEXT): ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it", "mixtral-8x7b-32768"],
            (Modality.AUDIO, Modality.TEXT): ["whisper-large-v3", "whisper-large-v3-turbo"],
        }

    def get_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="llama-3.3-70b-versatile", name="Llama 3.3 70B", provider="groq", modalities=["text→text"], context_window=128000, max_output_tokens=32768),
            ModelInfo(id="llama-3.1-8b-instant", name="Llama 3.1 8B", provider="groq", modalities=["text→text"], context_window=131072, max_output_tokens=8192),
            ModelInfo(id="gemma2-9b-it", name="Gemma 2 9B", provider="groq", modalities=["text→text"], context_window=8192, max_output_tokens=8192),
            ModelInfo(id="mixtral-8x7b-32768", name="Mixtral 8x7B", provider="groq", modalities=["text→text"], context_window=32768, max_output_tokens=32768),
            ModelInfo(id="whisper-large-v3", name="Whisper Large V3", provider="groq", modalities=["audio→text"], context_window=None, max_output_tokens=None),
            ModelInfo(id="whisper-large-v3-turbo", name="Whisper Large V3 Turbo", provider="groq", modalities=["audio→text"], context_window=None, max_output_tokens=None),
        ]

    @with_retry()
    async def chat(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse:
        payload = {
            "model": req.model or "llama-3.3-70b-versatile",
            "messages": req.messages or [{"role": "user", "content": req.prompt}],
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }
        resp = await self.client.post("/v1/chat/completions", json=payload, headers=self._headers(api_key))
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {})
        return UnifiedResponse(
            content=data["choices"][0]["message"]["content"],
            model=data.get("model"),
            provider="groq",
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )

    async def stream_chat(self, req: UnifiedRequest, api_key: str) -> AsyncIterator[Chunk]:
        payload = {
            "model": req.model or "llama-3.3-70b-versatile",
            "messages": req.messages or [{"role": "user", "content": req.prompt}],
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
            "stream": True,
        }
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
                data = json.loads(data_str)
                delta = data["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content or data["choices"][0].get("finish_reason"):
                    yield Chunk(content=content or "", finish_reason=data["choices"][0].get("finish_reason"), model=data.get("model"))

    @with_retry()
    async def speech_to_text(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse:
        headers = {"Authorization": f"Bearer {api_key}"}
        files = {"file": ("audio.webm", req.input_data, "audio/webm")}
        data = {"model": req.model or "whisper-large-v3-turbo"}
        resp = await self.client.post("/v1/audio/transcriptions", data=data, files=files, headers=headers)
        resp.raise_for_status()
        result = resp.json()
        return UnifiedResponse(content=result["text"], model=data["model"], provider="groq")
