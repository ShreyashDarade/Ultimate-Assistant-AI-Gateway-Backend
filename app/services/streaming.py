"""SSE and WebSocket streaming — pass-through, no buffering.

The goal: provider chunk in → serialize with orjson → flush out immediately.
This is where time-to-first-token is preserved.
"""

import json
import uuid
from collections.abc import AsyncIterator

import orjson
from fastapi import WebSocket
from starlette.responses import StreamingResponse

from app.core.logging import get_logger
from app.providers.base import ChatCapable
from app.providers.registry import ProviderRegistry
from app.schemas.provider import Chunk, UnifiedRequest
from app.services.key_service import KeyService

logger = get_logger(__name__)


async def sse_stream(
    provider_name: str,
    req: UnifiedRequest,
    api_key: str,
    registry: ProviderRegistry,
) -> AsyncIterator[bytes]:
    """Yield SSE-formatted chunks from a chat provider."""
    provider = registry.get_provider(provider_name)
    assert isinstance(provider, ChatCapable)

    async for chunk in provider.stream_chat(req, api_key):
        event_data = orjson.dumps({
            "content": chunk.content,
            "finish_reason": chunk.finish_reason,
            "model": chunk.model,
        })
        yield b"data: " + event_data + b"\n\n"

    yield b"data: [DONE]\n\n"


def create_sse_response(
    provider_name: str,
    req: UnifiedRequest,
    api_key: str,
    registry: ProviderRegistry,
) -> StreamingResponse:
    return StreamingResponse(
        sse_stream(provider_name, req, api_key, registry),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def websocket_chat(
    ws: WebSocket,
    user_id: uuid.UUID,
    registry: ProviderRegistry,
    key_service: KeyService,
):
    """Handle WebSocket chat — receive messages, stream responses."""
    await ws.accept()

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)

            provider_name = data.get("provider", "openai")
            model = data.get("model")
            messages = data.get("messages", [])

            # Get API key
            api_key = await key_service.get_decrypted_key(user_id, provider_name)

            req = UnifiedRequest(
                messages=messages,
                model=model,
                temperature=data.get("temperature", 0.7),
                max_tokens=data.get("max_tokens"),
                stream=True,
            )

            provider = registry.get_provider(provider_name)
            if not isinstance(provider, ChatCapable):
                await ws.send_json({"error": f"Provider {provider_name} does not support chat"})
                continue

            async for chunk in provider.stream_chat(req, api_key):
                await ws.send_bytes(orjson.dumps({
                    "content": chunk.content,
                    "finish_reason": chunk.finish_reason,
                    "model": chunk.model,
                }))

            await ws.send_bytes(orjson.dumps({"done": True}))

    except Exception as e:
        logger.warning("websocket_error", error=str(e))
    finally:
        try:
            await ws.close()
        except Exception:
            pass
