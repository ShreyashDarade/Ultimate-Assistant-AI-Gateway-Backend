"""Tests for the modality router."""

import pytest

from app.providers.capabilities import Modality, build_capability_map


def test_modality_enum():
    assert Modality.TEXT.value == "text"
    assert Modality.IMAGE.value == "image"
    assert Modality.AUDIO.value == "audio"
    assert Modality.VIDEO.value == "video"
    assert Modality.VECTOR.value == "vector"


def test_build_capability_map_empty():
    cap_map = build_capability_map({})
    assert cap_map == {}


class MockAdapter:
    def get_capabilities(self):
        return {
            (Modality.TEXT, Modality.TEXT): ["model-a", "model-b"],
            (Modality.TEXT, Modality.IMAGE): ["model-c"],
        }


def test_build_capability_map():
    adapters = {"test_provider": MockAdapter()}
    cap_map = build_capability_map(adapters)

    assert (Modality.TEXT, Modality.TEXT) in cap_map
    assert len(cap_map[(Modality.TEXT, Modality.TEXT)]) == 2
    assert ("test_provider", "model-a") in cap_map[(Modality.TEXT, Modality.TEXT)]
    assert (Modality.TEXT, Modality.IMAGE) in cap_map
    assert len(cap_map[(Modality.TEXT, Modality.IMAGE)]) == 1
