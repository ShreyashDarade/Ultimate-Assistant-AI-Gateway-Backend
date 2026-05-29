from app.core.logging import get_logger
from app.providers.base import BaseProvider
from app.providers.capabilities import CapabilityMap, build_capability_map
from app.providers.client_pool import ClientPool

# Import all adapters
from app.providers.openai.adapter import OpenAIAdapter
from app.providers.anthropic.adapter import AnthropicAdapter
from app.providers.google.adapter import GoogleAdapter
from app.providers.xai.adapter import XAIAdapter
from app.providers.mistral.adapter import MistralAdapter
from app.providers.cohere.adapter import CohereAdapter
from app.providers.groq.adapter import GroqAdapter
from app.providers.deepseek.adapter import DeepSeekAdapter
from app.providers.elevenlabs.adapter import ElevenLabsAdapter
from app.providers.replicate.adapter import ReplicateAdapter
from app.providers.stability.adapter import StabilityAdapter
from app.providers.fal.adapter import FalAdapter

logger = get_logger(__name__)

ADAPTER_CLASSES: list[type[BaseProvider]] = [
    OpenAIAdapter,
    AnthropicAdapter,
    GoogleAdapter,
    XAIAdapter,
    MistralAdapter,
    CohereAdapter,
    GroqAdapter,
    DeepSeekAdapter,
    ElevenLabsAdapter,
    ReplicateAdapter,
    StabilityAdapter,
    FalAdapter,
]


class ProviderRegistry:
    """Loads all provider adapters and builds the capability map at startup."""

    def __init__(self, client_pool: ClientPool):
        self.client_pool = client_pool
        self.providers: dict[str, BaseProvider] = {}
        self.capability_map: CapabilityMap = {}

    def load_all(self) -> None:
        for cls in ADAPTER_CLASSES:
            try:
                client = self.client_pool.get(cls.name)
                adapter = cls(client)
                self.providers[adapter.name] = adapter
                logger.info("provider_loaded", provider=adapter.name)
            except Exception as e:
                logger.warning("provider_load_failed", provider=cls.name, error=str(e))

        self.capability_map = build_capability_map(self.providers)
        total_caps = sum(len(v) for v in self.capability_map.values())
        logger.info("capability_map_built", conversions=len(self.capability_map), total_entries=total_caps)

    def get_provider(self, name: str) -> BaseProvider | None:
        return self.providers.get(name)

    def get_capable_providers(self, input_mod: str, output_mod: str) -> list[tuple[str, str]]:
        """Return [(provider_name, model_id)] for a given modality conversion."""
        from app.providers.capabilities import Modality
        key = (Modality(input_mod), Modality(output_mod))
        return self.capability_map.get(key, [])
