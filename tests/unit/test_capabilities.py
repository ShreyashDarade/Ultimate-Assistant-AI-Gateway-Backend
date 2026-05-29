"""Tests for provider capabilities."""

import pytest

from app.providers.openai.adapter import OpenAIAdapter
from app.providers.anthropic.adapter import AnthropicAdapter
from app.providers.google.adapter import GoogleAdapter
from app.providers.capabilities import Modality


class TestOpenAICapabilities:
    def test_has_chat(self):
        caps = OpenAIAdapter.__dict__  # Check class has methods
        assert "chat" in caps
        assert "stream_chat" in caps

    def test_capabilities_declared(self):
        # Can't instantiate without client, but can check class
        import httpx
        client = httpx.AsyncClient()
        adapter = OpenAIAdapter(client)
        caps = adapter.get_capabilities()
        assert (Modality.TEXT, Modality.TEXT) in caps
        assert (Modality.TEXT, Modality.IMAGE) in caps
        assert (Modality.TEXT, Modality.AUDIO) in caps
        assert (Modality.AUDIO, Modality.TEXT) in caps
        assert (Modality.TEXT, Modality.VECTOR) in caps


class TestAnthropicCapabilities:
    def test_capabilities_declared(self):
        import httpx
        client = httpx.AsyncClient()
        adapter = AnthropicAdapter(client)
        caps = adapter.get_capabilities()
        assert (Modality.TEXT, Modality.TEXT) in caps
        assert (Modality.IMAGE, Modality.TEXT) in caps


class TestGoogleCapabilities:
    def test_capabilities_declared(self):
        import httpx
        client = httpx.AsyncClient()
        adapter = GoogleAdapter(client)
        caps = adapter.get_capabilities()
        assert (Modality.TEXT, Modality.TEXT) in caps
        assert (Modality.TEXT, Modality.IMAGE) in caps
        assert (Modality.TEXT, Modality.VECTOR) in caps
