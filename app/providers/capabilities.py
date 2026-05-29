from enum import Enum


class Modality(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    VECTOR = "vector"


# A conversion is (input_modality, output_modality)
ModalityPair = tuple[Modality, Modality]


# Capability map: (input, output) → list of (provider_name, model_id)
CapabilityMap = dict[ModalityPair, list[tuple[str, str]]]


def build_capability_map(providers: dict) -> CapabilityMap:
    """Build a capability map from all registered providers."""
    cap_map: CapabilityMap = {}
    for provider_name, adapter in providers.items():
        for modality_pair, models in adapter.get_capabilities().items():
            if modality_pair not in cap_map:
                cap_map[modality_pair] = []
            for model_id in models:
                cap_map[modality_pair].append((provider_name, model_id))
    return cap_map
