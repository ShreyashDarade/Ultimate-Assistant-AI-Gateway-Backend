"""Ollama adapter — local LLM inference via Ollama.

Ollama runs locally and provides an OpenAI-compatible API.
This adapter supports:
  - Chat / streaming chat
  - Vision (via LLaVA or similar multimodal models)
  - Embeddings (via nomic-embed-text or similar)

Key differences from cloud providers:
  - No API key required (pass any string, or "ollama" as placeholder)
  - Base URL defaults to http://localhost:11434
  - Models are pulled/managed locally via `ollama pull <model>`
"""

import json
from collections.abc import AsyncIterator

import httpx

from app.providers.base import (
    BaseProvider,
    ChatCapable,
    EmbedCapable,
    VisionCapable,
)
from app.providers.capabilities import Modality, ModalityPair
from app.providers.ollama.mapping import (
    from_chat_response,
    from_stream_chunk,
    to_chat_request,
    to_embedding_request,
    to_vision_request,
)
from app.providers.retry import with_retry
from app.schemas.provider import Chunk, ModelInfo, UnifiedRequest, UnifiedResponse


class OllamaAdapter(BaseProvider, ChatCapable, VisionCapable, EmbedCapable):
    """Adapter for locally-running Ollama instances.

    Ollama is free and open-source. Users can run LLMs like Llama 3, Mistral,
    Phi, Gemma, Code Llama, etc. locally and route requests through this gateway.
    """

    name = "ollama"
    base_url = "http://localhost:11434"

    def _headers(self, api_key: str) -> dict:
        # Ollama does not require auth, but we maintain the interface.
        headers = {"Content-Type": "application/json"}
        if api_key and api_key != "ollama":
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def get_capabilities(self) -> dict[ModalityPair, list[str]]:
        return {
            (Modality.TEXT, Modality.TEXT): [
                "llama3.2",
                "llama3.2:1b",
                "llama3.1",
                "llama3.1:70b",
                "mistral",
                "mistral-nemo",
                "phi4",
                "gemma3",
                "gemma3:12b",
                "qwen3",
                "qwen3:8b",
                "deepseek-r1",
                "deepseek-r1:8b",
                "codellama",
                "command-r",
            ],
            (Modality.IMAGE, Modality.TEXT): [
                "llava",
                "llava:13b",
                "llava-llama3",
                "moondream",
            ],
            (Modality.TEXT, Modality.VECTOR): [
                "nomic-embed-text",
                "mxbai-embed-large",
                "all-minilm",
            ],
        }

    def get_models(self) -> list[ModelInfo]:
        return [
            # Chat models
            ModelInfo(
                id="llama3.2", name="Llama 3.2 3B", provider="ollama",
                modalities=["text→text"], context_window=131072,
                max_output_tokens=8192, supports_tools=True, supports_streaming=True,
            ),
            ModelInfo(
                id="llama3.2:1b", name="Llama 3.2 1B", provider="ollama",
                modalities=["text→text"], context_window=131072,
                max_output_tokens=8192, supports_streaming=True,
            ),
            ModelInfo(
                id="llama3.1", name="Llama 3.1 8B", provider="ollama",
                modalities=["text→text"], context_window=131072,
                max_output_tokens=8192, supports_tools=True, supports_streaming=True,
            ),
            ModelInfo(
                id="llama3.1:70b", name="Llama 3.1 70B", provider="ollama",
                modalities=["text→text"], context_window=131072,
                max_output_tokens=8192, supports_tools=True, supports_streaming=True,
            ),
            ModelInfo(
                id="mistral", name="Mistral 7B", provider="ollama",
                modalities=["text→text"], context_window=32768,
                max_output_tokens=4096, supports_streaming=True,
            ),
            ModelInfo(
                id="mistral-nemo", name="Mistral Nemo 12B", provider="ollama",
                modalities=["text→text"], context_window=131072,
                max_output_tokens=4096, supports_tools=True, supports_streaming=True,
            ),
            ModelInfo(
                id="phi4", name="Phi-4 14B", provider="ollama",
                modalities=["text→text"], context_window=16384,
                max_output_tokens=4096, supports_streaming=True,
            ),
            ModelInfo(
                id="gemma3", name="Gemma 3 4B", provider="ollama",
                modalities=["text→text"], context_window=131072,
                max_output_tokens=8192, supports_streaming=True,
            ),
            ModelInfo(
                id="gemma3:12b", name="Gemma 3 12B", provider="ollama",
                modalities=["text→text"], context_window=131072,
                max_output_tokens=8192, supports_streaming=True,
            ),
            ModelInfo(
                id="qwen3", name="Qwen 3 4B", provider="ollama",
                modalities=["text→text"], context_window=40960,
                max_output_tokens=4096, supports_tools=True, supports_streaming=True,
            ),
            ModelInfo(
                id="qwen3:8b", name="Qwen 3 8B", provider="ollama",
                modalities=["text→text"], context_window=40960,
                max_output_tokens=4096, supports_tools=True, supports_streaming=True,
            ),
            ModelInfo(
                id="deepseek-r1", name="DeepSeek R1 7B", provider="ollama",
                modalities=["text→text"], context_window=65536,
                max_output_tokens=8192, supports_streaming=True,
            ),
            ModelInfo(
                id="deepseek-r1:8b", name="DeepSeek R1 8B", provider="ollama",
                modalities=["text→text"], context_window=65536,
                max_output_tokens=8192, supports_streaming=True,
            ),
            ModelInfo(
                id="codellama", name="Code Llama 7B", provider="ollama",
                modalities=["text→text"], context_window=16384,
                max_output_tokens=4096, supports_streaming=True,
            ),
            ModelInfo(
                id="command-r", name="Command R", provider="ollama",
                modalities=["text→text"], context_window=131072,
                max_output_tokens=4096, supports_tools=True, supports_streaming=True,
            ),
            # Vision models
            ModelInfo(
                id="llava", name="LLaVA 7B", provider="ollama",
                modalities=["image→text"], context_window=4096,
                supports_vision=True, supports_streaming=True,
            ),
            ModelInfo(
                id="llava:13b", name="LLaVA 13B", provider="ollama",
                modalities=["image→text"], context_window=4096,
                supports_vision=True, supports_streaming=True,
            ),
            ModelInfo(
                id="llava-llama3", name="LLaVA Llama 3", provider="ollama",
                modalities=["image→text"], context_window=8192,
                supports_vision=True, supports_streaming=True,
            ),
            ModelInfo(
                id="moondream", name="Moondream 2", provider="ollama",
                modalities=["image→text"], context_window=2048,
                supports_vision=True, supports_streaming=True,
            ),
            # Embedding models
            ModelInfo(
                id="nomic-embed-text", name="Nomic Embed Text", provider="ollama",
                modalities=["text→vector"], context_window=8192,
            ),
            ModelInfo(
                id="mxbai-embed-large", name="mxbai Embed Large", provider="ollama",
                modalities=["text→vector"], context_window=512,
            ),
            ModelInfo(
                id="all-minilm", name="all-MiniLM-L6-v2", provider="ollama",
                modalities=["text→vector"], context_window=512,
            ),
        ]

    @with_retry(max_retries=2, backoff_base=0.3)
    async def chat(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse:
        payload = to_chat_request(req)
        payload["stream"] = False
        resp = await self.client.post(
            "/v1/chat/completions", json=payload, headers=self._headers(api_key)
        )
        resp.raise_for_status()
        return from_chat_response(resp.json())

    async def stream_chat(self, req: UnifiedRequest, api_key: str) -> AsyncIterator[Chunk]:
        payload = to_chat_request(req)
        payload["stream"] = True
        async with self.client.stream(
            "POST",
            "/v1/chat/completions",
            json=payload,
            headers=self._headers(api_key),
            timeout=120.0,
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

    @with_retry(max_retries=2, backoff_base=0.3)
    async def image_to_text(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse:
        payload = to_vision_request(req)
        resp = await self.client.post(
            "/v1/chat/completions", json=payload, headers=self._headers(api_key)
        )
        resp.raise_for_status()
        return from_chat_response(resp.json())

    @with_retry(max_retries=2, backoff_base=0.3)
    async def embed(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse:
        payload = to_embedding_request(req)
        resp = await self.client.post(
            "/v1/embeddings", json=payload, headers=self._headers(api_key)
        )
        resp.raise_for_status()
        data = resp.json()
        embedding = data["data"][0]["embedding"]
        return UnifiedResponse(
            content=json.dumps(embedding),
            model=payload["model"],
            provider="ollama",
            input_tokens=data.get("usage", {}).get("total_tokens"),
        )

    async def validate_key(self, api_key: str) -> bool:
        """Ollama doesn't need keys — just check if the server is reachable."""
        try:
            resp = await self.client.get("/api/tags")
            return resp.status_code == 200
        except Exception:
            return False
