"""Cohere adapter — chat, embeddings, rerank."""

import json
from collections.abc import AsyncIterator

from app.providers.base import BaseProvider, ChatCapable, EmbedCapable
from app.providers.capabilities import Modality, ModalityPair
from app.providers.retry import with_retry
from app.schemas.provider import Chunk, ModelInfo, UnifiedRequest, UnifiedResponse


class CohereAdapter(BaseProvider, ChatCapable, EmbedCapable):
    name = "cohere"
    base_url = "https://api.cohere.com"

    def _headers(self, api_key: str) -> dict:
        return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def get_capabilities(self) -> dict[ModalityPair, list[str]]:
        return {
            (Modality.TEXT, Modality.TEXT): ["command-r-plus", "command-r", "command-a-03-2025"],
            (Modality.TEXT, Modality.VECTOR): ["embed-v4.0", "embed-english-v3.0", "embed-multilingual-v3.0"],
        }

    def get_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="command-r-plus", name="Command R+", provider="cohere", modalities=["text→text"], context_window=128000, max_output_tokens=4096),
            ModelInfo(id="command-r", name="Command R", provider="cohere", modalities=["text→text"], context_window=128000, max_output_tokens=4096),
            ModelInfo(id="command-a-03-2025", name="Command A", provider="cohere", modalities=["text→text"], context_window=256000, max_output_tokens=8192),
            ModelInfo(id="embed-v4.0", name="Embed v4.0", provider="cohere", modalities=["text→vector"], context_window=128000, max_output_tokens=None),
            ModelInfo(id="embed-english-v3.0", name="Embed English v3.0", provider="cohere", modalities=["text→vector"], context_window=512, max_output_tokens=None),
            ModelInfo(id="embed-multilingual-v3.0", name="Embed Multilingual v3.0", provider="cohere", modalities=["text→vector"], context_window=512, max_output_tokens=None),
        ]

    @with_retry()
    async def chat(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse:
        messages = req.messages or [{"role": "user", "content": req.prompt}]
        payload = {
            "model": req.model or "command-r",
            "messages": messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }
        resp = await self.client.post("/v2/chat", json=payload, headers=self._headers(api_key))
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {}).get("tokens", {})
        return UnifiedResponse(
            content=data.get("message", {}).get("content", [{}])[0].get("text", ""),
            model=data.get("model"),
            provider="cohere",
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )

    async def stream_chat(self, req: UnifiedRequest, api_key: str) -> AsyncIterator[Chunk]:
        messages = req.messages or [{"role": "user", "content": req.prompt}]
        payload = {
            "model": req.model or "command-r",
            "messages": messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
            "stream": True,
        }
        async with self.client.stream(
            "POST", "/v2/chat", json=payload, headers=self._headers(api_key)
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = json.loads(line[6:])
                event_type = data.get("type")
                if event_type == "content-delta":
                    delta = data.get("delta", {}).get("message", {}).get("content", {}).get("text", "")
                    if delta:
                        yield Chunk(content=delta, model=req.model)
                elif event_type == "message-end":
                    yield Chunk(content="", finish_reason="stop", model=req.model)

    @with_retry()
    async def embed(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse:
        text = req.prompt or (req.messages[-1]["content"] if req.messages else "")
        payload = {
            "model": req.model or "embed-v4.0",
            "texts": [text],
            "input_type": "search_document",
        }
        resp = await self.client.post("/v2/embed", json=payload, headers=self._headers(api_key))
        resp.raise_for_status()
        data = resp.json()
        embedding = data["embeddings"]["float"][0]
        return UnifiedResponse(content=json.dumps(embedding), model=payload["model"], provider="cohere")
