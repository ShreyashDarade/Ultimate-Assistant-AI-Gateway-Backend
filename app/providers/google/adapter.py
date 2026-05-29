"""Google adapter — Gemini chat, Imagen image gen, vision, embeddings."""

import json
from collections.abc import AsyncIterator

from app.providers.base import (
    BaseProvider, ChatCapable, EmbedCapable, ImageGenCapable, VisionCapable,
)
from app.providers.capabilities import Modality, ModalityPair
from app.providers.retry import with_retry
from app.schemas.provider import Chunk, MediaResult, ModelInfo, UnifiedRequest, UnifiedResponse


class GoogleAdapter(BaseProvider, ChatCapable, ImageGenCapable, VisionCapable, EmbedCapable):
    name = "google"
    base_url = "https://generativelanguage.googleapis.com"

    def _headers(self, api_key: str) -> dict:
        return {"Content-Type": "application/json"}

    def get_capabilities(self) -> dict[ModalityPair, list[str]]:
        return {
            (Modality.TEXT, Modality.TEXT): ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"],
            (Modality.TEXT, Modality.IMAGE): ["imagen-4"],
            (Modality.IMAGE, Modality.TEXT): ["gemini-2.5-pro", "gemini-2.5-flash"],
            (Modality.TEXT, Modality.VECTOR): ["text-embedding-004"],
        }

    def get_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="gemini-2.5-pro", name="Gemini 2.5 Pro", provider="google", modalities=["text→text", "image→text"], context_window=1048576, max_output_tokens=65536),
            ModelInfo(id="gemini-2.5-flash", name="Gemini 2.5 Flash", provider="google", modalities=["text→text", "image→text"], context_window=1048576, max_output_tokens=65536),
            ModelInfo(id="gemini-2.0-flash", name="Gemini 2.0 Flash", provider="google", modalities=["text→text"], context_window=1048576, max_output_tokens=8192),
            ModelInfo(id="imagen-4", name="Imagen 4", provider="google", modalities=["text→image"], context_window=None, max_output_tokens=None),
            ModelInfo(id="text-embedding-004", name="Text Embedding 004", provider="google", modalities=["text→vector"], context_window=2048, max_output_tokens=None),
        ]

    def _build_contents(self, req: UnifiedRequest) -> list[dict]:
        contents = []
        for msg in (req.messages or [{"role": "user", "content": req.prompt}]):
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        return contents

    @with_retry()
    async def chat(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse:
        model = req.model or "gemini-2.5-flash"
        contents = self._build_contents(req)
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": req.temperature,
                "maxOutputTokens": req.max_tokens or 4096,
            },
        }
        resp = await self.client.post(
            f"/v1beta/models/{model}:generateContent?key={api_key}",
            json=payload,
            headers=self._headers(api_key),
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        usage = data.get("usageMetadata", {})
        return UnifiedResponse(
            content=text,
            model=model,
            provider="google",
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
        )

    async def stream_chat(self, req: UnifiedRequest, api_key: str) -> AsyncIterator[Chunk]:
        model = req.model or "gemini-2.5-flash"
        contents = self._build_contents(req)
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": req.temperature,
                "maxOutputTokens": req.max_tokens or 4096,
            },
        }
        async with self.client.stream(
            "POST",
            f"/v1beta/models/{model}:streamGenerateContent?alt=sse&key={api_key}",
            json=payload,
            headers=self._headers(api_key),
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = json.loads(line[6:])
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    for part in parts:
                        if "text" in part:
                            yield Chunk(content=part["text"], model=model)
                    if candidates[0].get("finishReason"):
                        yield Chunk(content="", finish_reason=candidates[0]["finishReason"], model=model)

    @with_retry()
    async def text_to_image(self, req: UnifiedRequest, api_key: str) -> MediaResult:
        model = req.model or "imagen-4"
        payload = {
            "instances": [{"prompt": req.prompt}],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": req.options.get("aspect_ratio", "1:1") if req.options else "1:1",
            },
        }
        resp = await self.client.post(
            f"/v1beta/models/{model}:predict?key={api_key}",
            json=payload,
            headers=self._headers(api_key),
        )
        resp.raise_for_status()
        data = resp.json()
        # Returns base64 image data — caller uploads to S3
        return MediaResult(
            file_url="",  # set after S3 upload
            mime_type="image/png",
            model=model,
            provider="google",
        )

    @with_retry()
    async def image_to_text(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse:
        model = req.model or "gemini-2.5-flash"
        contents = [
            {
                "role": "user",
                "parts": [
                    {"text": req.prompt or "Describe this image"},
                    {"inlineData": {"mimeType": "image/jpeg", "data": ""}} if not req.input_url
                    else {"fileData": {"mimeType": "image/jpeg", "fileUri": req.input_url}},
                ],
            }
        ]
        payload = {"contents": contents}
        resp = await self.client.post(
            f"/v1beta/models/{model}:generateContent?key={api_key}",
            json=payload,
            headers=self._headers(api_key),
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return UnifiedResponse(content=text, model=model, provider="google")

    @with_retry()
    async def embed(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse:
        model = req.model or "text-embedding-004"
        text = req.prompt or (req.messages[-1]["content"] if req.messages else "")
        payload = {"content": {"parts": [{"text": text}]}}
        resp = await self.client.post(
            f"/v1beta/models/{model}:embedContent?key={api_key}",
            json=payload,
            headers=self._headers(api_key),
        )
        resp.raise_for_status()
        data = resp.json()
        embedding = data["embedding"]["values"]
        return UnifiedResponse(content=json.dumps(embedding), model=model, provider="google")
