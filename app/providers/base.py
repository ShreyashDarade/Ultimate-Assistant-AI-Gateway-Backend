from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

import httpx

from app.providers.capabilities import ModalityPair
from app.schemas.provider import Chunk, MediaResult, ModelInfo, UnifiedRequest, UnifiedResponse


@runtime_checkable
class ChatCapable(Protocol):
    async def chat(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse: ...
    async def stream_chat(self, req: UnifiedRequest, api_key: str) -> AsyncIterator[Chunk]: ...


@runtime_checkable
class ImageGenCapable(Protocol):
    async def text_to_image(self, req: UnifiedRequest, api_key: str) -> MediaResult: ...


@runtime_checkable
class VisionCapable(Protocol):
    async def image_to_text(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse: ...


@runtime_checkable
class TTSCapable(Protocol):
    async def text_to_speech(self, req: UnifiedRequest, api_key: str) -> MediaResult: ...


@runtime_checkable
class STTCapable(Protocol):
    async def speech_to_text(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse: ...


@runtime_checkable
class EmbedCapable(Protocol):
    async def embed(self, req: UnifiedRequest, api_key: str) -> UnifiedResponse: ...


@runtime_checkable
class VideoGenCapable(Protocol):
    async def text_to_video(self, req: UnifiedRequest, api_key: str) -> MediaResult: ...
    async def image_to_video(self, req: UnifiedRequest, api_key: str) -> MediaResult: ...


class BaseProvider(ABC):
    """Base class for all provider adapters."""

    name: str  # e.g. "openai", "anthropic"
    base_url: str

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    @abstractmethod
    def get_capabilities(self) -> dict[ModalityPair, list[str]]:
        """Return {(input_mod, output_mod): [model_ids]} this provider supports."""
        ...

    @abstractmethod
    def get_models(self) -> list[ModelInfo]:
        """Return model info for this provider."""
        ...

    async def validate_key(self, api_key: str) -> bool:
        """Quick test call to validate the API key works.

        Only providers that implement ChatCapable can be validated this way;
        for others we cannot cheaply verify the key, so we report True.
        """
        if not isinstance(self, ChatCapable):
            return True
        try:
            await self.chat(
                UnifiedRequest(messages=[{"role": "user", "content": "hi"}], max_tokens=1),
                api_key,
            )
            return True
        except Exception:
            return False
