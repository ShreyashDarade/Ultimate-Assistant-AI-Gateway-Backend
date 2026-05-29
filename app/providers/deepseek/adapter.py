"""DeepSeek adapter — chat (OpenAI-compatible API)."""

import json
from collections.abc import AsyncIterator

from app.providers.base import BaseProvider, ChatCapable
from app.providers.capabilities import Modality, ModalityPair
from app.providers.retry import with_retry
from app.schemas.provider import Chunk, ModelInfo, UnifiedRequest, UnifiedResponse


class DeepSeekAdapter(BaseProvider, ChatCapable):
    name = "deepseek"
    base_url = "https://api.deepseek.com"

    def _headers(self, api_key: str) -> dict:
        return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def get_capabilities(self) -> dict[ModalityPair, list[str]]:
        return {
            (Modality.TEXT, Modality.TEXT): ["deepseek-chat", "deepseek-reasoner"],
        }

    def get_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="deepseek-chat", name="DeepSeek V3", provider="deepseek", modalities=["text→text"], context_window=65536, max_output_tokens=8192),
            ModelInfo(id="deepseek-reasoner", name="DeepSeek R1", provider="deepseek", modalities=["text→text"], context_window=65536, max_output_tokens=8192),
        ]

    @with_retry()
    async def chat(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse:
        payload = {
            "model": req.model or "deepseek-chat",
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
            provider="deepseek",
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )

    async def stream_chat(self, req: UnifiedRequest, api_key: str) -> AsyncIterator[Chunk]:
        payload = {
            "model": req.model or "deepseek-chat",
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
