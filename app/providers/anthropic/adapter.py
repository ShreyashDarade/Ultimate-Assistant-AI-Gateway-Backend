"""Anthropic adapter — chat (Claude), vision."""

import json
from collections.abc import AsyncIterator

from app.providers.base import BaseProvider, ChatCapable, VisionCapable
from app.providers.capabilities import Modality, ModalityPair
from app.providers.retry import with_retry
from app.schemas.provider import Chunk, ModelInfo, UnifiedRequest, UnifiedResponse


class AnthropicAdapter(BaseProvider, ChatCapable, VisionCapable):
    name = "anthropic"
    base_url = "https://api.anthropic.com"

    def _headers(self, api_key: str) -> dict:
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def get_capabilities(self) -> dict[ModalityPair, list[str]]:
        return {
            (Modality.TEXT, Modality.TEXT): [
                "claude-sonnet-4-20250514", "claude-opus-4-20250514",
                "claude-3-5-haiku-20241022",
            ],
            (Modality.IMAGE, Modality.TEXT): [
                "claude-sonnet-4-20250514", "claude-opus-4-20250514",
            ],
        }

    def get_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="claude-sonnet-4-20250514", name="Claude Sonnet 4", provider="anthropic", modalities=["text→text", "image→text"], context_window=200000, max_output_tokens=64000),
            ModelInfo(id="claude-opus-4-20250514", name="Claude Opus 4", provider="anthropic", modalities=["text→text", "image→text"], context_window=200000, max_output_tokens=32000),
            ModelInfo(id="claude-3-5-haiku-20241022", name="Claude 3.5 Haiku", provider="anthropic", modalities=["text→text"], context_window=200000, max_output_tokens=8192),
        ]

    def _build_messages(self, req: UnifiedRequest) -> tuple[str | None, list[dict]]:
        system = None
        messages = []
        for msg in (req.messages or [{"role": "user", "content": req.prompt}]):
            if msg["role"] == "system":
                system = msg["content"]
            else:
                messages.append({"role": msg["role"], "content": msg["content"]})
        return system, messages

    @with_retry()
    async def chat(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse:
        system, messages = self._build_messages(req)
        payload: dict = {
            "model": req.model or "claude-sonnet-4-20250514",
            "messages": messages,
            "max_tokens": req.max_tokens or 4096,
            "temperature": req.temperature,
        }
        if system:
            payload["system"] = system

        resp = await self.client.post("/v1/messages", json=payload, headers=self._headers(api_key))
        resp.raise_for_status()
        data = resp.json()
        return UnifiedResponse(
            content=data["content"][0]["text"],
            model=data.get("model"),
            provider="anthropic",
            input_tokens=data.get("usage", {}).get("input_tokens"),
            output_tokens=data.get("usage", {}).get("output_tokens"),
        )

    async def stream_chat(self, req: UnifiedRequest, api_key: str) -> AsyncIterator[Chunk]:
        system, messages = self._build_messages(req)
        payload: dict = {
            "model": req.model or "claude-sonnet-4-20250514",
            "messages": messages,
            "max_tokens": req.max_tokens or 4096,
            "temperature": req.temperature,
            "stream": True,
        }
        if system:
            payload["system"] = system

        async with self.client.stream(
            "POST", "/v1/messages", json=payload, headers=self._headers(api_key)
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = json.loads(line[6:])
                event_type = data.get("type")
                if event_type == "content_block_delta":
                    delta = data.get("delta", {})
                    if delta.get("type") == "text_delta":
                        yield Chunk(content=delta["text"], model=req.model)
                elif event_type == "message_stop":
                    yield Chunk(content="", finish_reason="stop", model=req.model)

    @with_retry()
    async def image_to_text(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": req.prompt or "Describe this image in detail."},
                    {
                        "type": "image",
                        "source": {"type": "url", "url": req.input_url},
                    },
                ],
            }
        ]
        payload = {
            "model": req.model or "claude-sonnet-4-20250514",
            "messages": messages,
            "max_tokens": req.max_tokens or 1024,
        }
        resp = await self.client.post("/v1/messages", json=payload, headers=self._headers(api_key))
        resp.raise_for_status()
        data = resp.json()
        return UnifiedResponse(
            content=data["content"][0]["text"],
            model=data.get("model"),
            provider="anthropic",
        )
