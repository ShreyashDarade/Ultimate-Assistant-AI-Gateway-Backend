"""xAI adapter — Grok chat + vision (OpenAI-compatible API)."""

import json
from collections.abc import AsyncIterator

from app.providers.base import BaseProvider, ChatCapable, VisionCapable
from app.providers.capabilities import Modality, ModalityPair
from app.providers.retry import with_retry
from app.schemas.provider import Chunk, ModelInfo, UnifiedRequest, UnifiedResponse


class XAIAdapter(BaseProvider, ChatCapable, VisionCapable):
    name = "xai"
    base_url = "https://api.x.ai"

    def _headers(self, api_key: str) -> dict:
        return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def get_capabilities(self) -> dict[ModalityPair, list[str]]:
        return {
            (Modality.TEXT, Modality.TEXT): ["grok-3", "grok-3-fast", "grok-3-mini", "grok-3-mini-fast"],
            (Modality.IMAGE, Modality.TEXT): ["grok-3", "grok-3-fast"],
        }

    def get_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="grok-3", name="Grok 3", provider="xai", modalities=["text→text", "image→text"], context_window=131072, max_output_tokens=16384),
            ModelInfo(id="grok-3-fast", name="Grok 3 Fast", provider="xai", modalities=["text→text", "image→text"], context_window=131072, max_output_tokens=16384),
            ModelInfo(id="grok-3-mini", name="Grok 3 Mini", provider="xai", modalities=["text→text"], context_window=131072, max_output_tokens=16384),
            ModelInfo(id="grok-3-mini-fast", name="Grok 3 Mini Fast", provider="xai", modalities=["text→text"], context_window=131072, max_output_tokens=16384),
        ]

    @with_retry()
    async def chat(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse:
        payload = {
            "model": req.model or "grok-3-fast",
            "messages": req.messages or [{"role": "user", "content": req.prompt}],
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
            "stream": False,
        }
        resp = await self.client.post("/v1/chat/completions", json=payload, headers=self._headers(api_key))
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {})
        return UnifiedResponse(
            content=data["choices"][0]["message"]["content"],
            model=data.get("model"),
            provider="xai",
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )

    async def stream_chat(self, req: UnifiedRequest, api_key: str) -> AsyncIterator[Chunk]:
        payload = {
            "model": req.model or "grok-3-fast",
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
                    yield Chunk(
                        content=content or "",
                        finish_reason=data["choices"][0].get("finish_reason"),
                        model=data.get("model"),
                    )

    @with_retry()
    async def image_to_text(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": req.prompt or "Describe this image"},
                    {"type": "image_url", "image_url": {"url": req.input_url}},
                ],
            }
        ]
        payload = {
            "model": req.model or "grok-3-fast",
            "messages": messages,
            "max_tokens": req.max_tokens or 1024,
        }
        resp = await self.client.post("/v1/chat/completions", json=payload, headers=self._headers(api_key))
        resp.raise_for_status()
        data = resp.json()
        return UnifiedResponse(
            content=data["choices"][0]["message"]["content"],
            model=data.get("model"),
            provider="xai",
        )
