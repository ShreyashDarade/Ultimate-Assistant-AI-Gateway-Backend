"""Modality router — the brain of any-to-any routing.

1. Determine requested (input → output) modalities
2. Look up capable (provider, model) pairs in capability map
3. Filter to providers the user has a key for (BYOK)
4. Rank by latency / error rate / cost
5. Dispatch through the chosen adapter with automatic failover
"""

import time
import uuid

from app.core.exceptions import CapabilityNotSupported, ProviderError, ProviderKeyMissing
from app.core.logging import get_logger
from app.core.telemetry import PROVIDER_LATENCY, PROVIDER_REQUEST_COUNT
from app.providers.base import (
    BaseProvider,
    ChatCapable,
    EmbedCapable,
    ImageGenCapable,
    STTCapable,
    TTSCapable,
    VideoGenCapable,
    VisionCapable,
)
from app.providers.capabilities import Modality
from app.providers.registry import ProviderRegistry
from app.schemas.provider import MediaResult, UnifiedRequest, UnifiedResponse
from app.services.key_service import KeyService
from app.services.ranker import ProviderRanker

logger = get_logger(__name__)


class ModalityRouter:
    def __init__(
        self,
        registry: ProviderRegistry,
        key_service: KeyService,
        ranker: ProviderRanker | None = None,
    ):
        self.registry = registry
        self.key_service = key_service
        self.ranker = ranker

    async def route(
        self,
        req: UnifiedRequest,
        user_id: uuid.UUID,
        input_modality: str,
        output_modality: str,
        preferred_provider: str | None = None,
        preferred_model: str | None = None,
    ) -> UnifiedResponse | MediaResult:
        # 1. Find capable providers
        capable = self.registry.get_capable_providers(input_modality, output_modality)
        if not capable:
            raise CapabilityNotSupported(input_modality, output_modality)

        # 2. Filter by user's keys
        user_providers = await self.key_service.get_user_providers(user_id)
        available = [(p, m) for p, m in capable if p in user_providers]
        if not available:
            providers_needed = list({p for p, _ in capable})
            raise ProviderKeyMissing(", ".join(providers_needed))

        # 3. Apply preference
        if preferred_provider:
            preferred = [(p, m) for p, m in available if p == preferred_provider]
            if preferred:
                available = preferred
        if preferred_model:
            model_match = [(p, m) for p, m in available if m == preferred_model]
            if model_match:
                available = model_match

        # 4. Rank by latency / error rate / cost
        if self.ranker and len(available) > 1:
            available = await self.ranker.rank(available)

        # 5. Dispatch with automatic failover
        last_error: Exception | None = None
        for provider_name, model_id in available:
            provider = self.registry.get_provider(provider_name)
            if not provider:
                continue

            api_key = await self.key_service.get_decrypted_key(user_id, provider_name)
            req.model = req.model or model_id

            start = time.monotonic()
            try:
                result = await self._dispatch(
                    provider, req, api_key, input_modality, output_modality
                )
                elapsed_ms = int((time.monotonic() - start) * 1000)

                # Record success metrics
                PROVIDER_REQUEST_COUNT.labels(
                    provider=provider_name,
                    model=model_id,
                    modality=f"{input_modality}→{output_modality}",
                    status="success",
                ).inc()
                PROVIDER_LATENCY.labels(
                    provider=provider_name, model=model_id
                ).observe(elapsed_ms / 1000)

                # Update ranker stats
                if self.ranker:
                    await self.ranker.record_success(provider_name, model_id, elapsed_ms)

                if isinstance(result, UnifiedResponse):
                    result.provider = provider_name
                    result.latency_ms = elapsed_ms
                elif isinstance(result, MediaResult):
                    result.latency_ms = elapsed_ms

                logger.info(
                    "routed",
                    provider=provider_name,
                    model=model_id,
                    latency_ms=elapsed_ms,
                )
                return result

            except ProviderError as e:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                PROVIDER_REQUEST_COUNT.labels(
                    provider=provider_name,
                    model=model_id,
                    modality=f"{input_modality}→{output_modality}",
                    status="error",
                ).inc()
                if self.ranker:
                    await self.ranker.record_failure(provider_name, model_id)

                last_error = e
                logger.warning(
                    "provider_failed_failover",
                    provider=provider_name,
                    model=model_id,
                    error=str(e),
                    remaining=len(available) - available.index((provider_name, model_id)) - 1,
                )
                continue

            except Exception as e:
                PROVIDER_REQUEST_COUNT.labels(
                    provider=provider_name,
                    model=model_id,
                    modality=f"{input_modality}→{output_modality}",
                    status="error",
                ).inc()
                if self.ranker:
                    await self.ranker.record_failure(provider_name, model_id)
                last_error = e
                logger.warning(
                    "provider_failed_failover",
                    provider=provider_name,
                    error=str(e),
                )
                continue

        # All providers failed
        if last_error:
            raise ProviderError("all", f"All providers failed. Last error: {last_error}")
        raise CapabilityNotSupported(input_modality, output_modality)

    async def _dispatch(
        self,
        provider: BaseProvider,
        req: UnifiedRequest,
        api_key: str,
        input_mod: str,
        output_mod: str,
    ) -> UnifiedResponse | MediaResult:
        in_m, out_m = Modality(input_mod), Modality(output_mod)

        if in_m == Modality.TEXT and out_m == Modality.TEXT:
            if not isinstance(provider, ChatCapable):
                raise CapabilityNotSupported(input_mod, output_mod)
            return await provider.chat(req, api_key)

        if in_m == Modality.TEXT and out_m == Modality.IMAGE:
            if not isinstance(provider, ImageGenCapable):
                raise CapabilityNotSupported(input_mod, output_mod)
            return await provider.text_to_image(req, api_key)

        if in_m == Modality.IMAGE and out_m == Modality.TEXT:
            if not isinstance(provider, VisionCapable):
                raise CapabilityNotSupported(input_mod, output_mod)
            return await provider.image_to_text(req, api_key)

        if in_m == Modality.TEXT and out_m == Modality.AUDIO:
            if not isinstance(provider, TTSCapable):
                raise CapabilityNotSupported(input_mod, output_mod)
            return await provider.text_to_speech(req, api_key)

        if in_m == Modality.AUDIO and out_m == Modality.TEXT:
            if not isinstance(provider, STTCapable):
                raise CapabilityNotSupported(input_mod, output_mod)
            return await provider.speech_to_text(req, api_key)

        if in_m == Modality.TEXT and out_m == Modality.VECTOR:
            if not isinstance(provider, EmbedCapable):
                raise CapabilityNotSupported(input_mod, output_mod)
            return await provider.embed(req, api_key)

        if in_m == Modality.TEXT and out_m == Modality.VIDEO:
            if not isinstance(provider, VideoGenCapable):
                raise CapabilityNotSupported(input_mod, output_mod)
            return await provider.text_to_video(req, api_key)

        if in_m == Modality.IMAGE and out_m == Modality.VIDEO:
            if not isinstance(provider, VideoGenCapable):
                raise CapabilityNotSupported(input_mod, output_mod)
            return await provider.image_to_video(req, api_key)

        raise CapabilityNotSupported(input_mod, output_mod)
