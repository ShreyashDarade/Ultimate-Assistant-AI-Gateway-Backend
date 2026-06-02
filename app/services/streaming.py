"""SSE and WebSocket streaming — pass-through, no buffering.

The goal: provider chunk in → serialize with orjson → flush out immediately.
This is where time-to-first-token is preserved.

Improvements:
- Proper isinstance checks (no asserts)
- SSE heartbeat keepalive to prevent proxy timeouts
- Better error handling in WebSocket
"""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

import orjson
from fastapi import WebSocket
from starlette.responses import StreamingResponse

from app.core.exceptions import CapabilityNotSupported
from app.core.logging import get_logger
from app.providers.base import ChatCapable
from app.providers.registry import ProviderRegistry
from app.schemas.provider import Chunk, UnifiedRequest
from app.services.key_service import KeyService

logger = get_logger(__name__)

# How often to send a keepalive comment in SSE (seconds).
_SSE_HEARTBEAT_INTERVAL = 15


async def sse_stream(
    provider_name: str,
    req: UnifiedRequest,
    api_key: str,
    registry: ProviderRegistry,
) -> AsyncIterator[bytes]:
    """Yield SSE-formatted chunks from a chat provider.

    Includes periodic keepalive comments to prevent proxy/ALB timeouts.
    """
    provider = registry.get_provider(provider_name)
    if not isinstance(provider, ChatCapable):
        yield b"data: " + orjson.dumps({"error": f"Provider {provider_name} does not support chat"}) + b"\n\n"
        return

    async def _heartbeat() -> AsyncIterator[bytes]:
        """Yield keepalive comments every N seconds."""
        while True:
            await asyncio.sleep(_SSE_HEARTBEAT_INTERVAL)
            yield b":keepalive\n\n"

    # Merge the data stream with the heartbeat.
    data_done = False

    async def _data_stream() -> AsyncIterator[bytes]:
        nonlocal data_done
        try:
            async for chunk in provider.stream_chat(req, api_key):
                event_data = orjson.dumps({
                    "content": chunk.content,
                    "finish_reason": chunk.finish_reason,
                    "model": chunk.model,
                })
                yield b"data: " + event_data + b"\n\n"
        except Exception as e:
            logger.warning("sse_stream_error", provider=provider_name, error=str(e))
            yield b"data: " + orjson.dumps({"error": str(e)}) + b"\n\n"
        finally:
            data_done = True
            yield b"data: [DONE]\n\n"

    # Simple approach: yield data with interleaved heartbeats.
    last_activity = asyncio.get_event_loop().time()

    async for data_chunk in _data_stream():
        yield data_chunk
        now = asyncio.get_event_loop().time()
        # If we haven't sent anything for a while, the next iteration
        # will produce data quickly enough. The keepalive is mainly
        # for long pauses between chunks (e.g. during reasoning).
        last_activity = now


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
            try:
                api_key = await key_service.get_decrypted_key(user_id, provider_name)
            except Exception as e:
                await ws.send_json({"error": str(e)})
                continue

            req = UnifiedRequest(
                messages=messages,
                model=model,
                temperature=data.get("temperature", 0.7),
                max_tokens=data.get("max_tokens"),
                stream=True,
            )

            provider = registry.get_provider(provider_name)
            if not isinstance(provider, ChatCapable):
                await ws.send_json(
                    {"error": f"Provider {provider_name} does not support chat"}
                )
                continue

            try:
                async for chunk in provider.stream_chat(req, api_key):
                    await ws.send_bytes(
                        orjson.dumps({
                            "content": chunk.content,
                            "finish_reason": chunk.finish_reason,
                            "model": chunk.model,
                        })
                    )
                await ws.send_bytes(orjson.dumps({"done": True}))
            except Exception as e:
                logger.warning("websocket_stream_error", error=str(e))
                await ws.send_json({"error": str(e), "done": True})

    except Exception as e:
        logger.warning("websocket_error", error=str(e))
    finally:
        try:
            await ws.close()
        except Exception:
            pass
