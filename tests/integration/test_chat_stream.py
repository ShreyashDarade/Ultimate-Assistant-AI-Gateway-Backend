"""Integration tests for chat streaming (requires mocking)."""

import pytest


@pytest.mark.skip(reason="Requires provider API key for full integration test")
async def test_chat_stream_sse(client, auth_headers):
    """Test SSE streaming returns proper event-stream."""
    resp = await client.post(
        "/v1/chat/stream",
        json={
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
