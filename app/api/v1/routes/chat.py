"""Chat routes — text↔text, streaming SSE + WebSocket."""

import uuid

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect

from app.api.v1.deps import (
    get_chat_service, get_current_user_id, get_key_service,
    get_registry, rate_limit,
)
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.services.streaming import create_sse_response, websocket_chat

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(rate_limit)])


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service),
):
    """Non-streaming chat — returns full response."""
    return await chat_service.chat(req, user_id)


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service),
):
    """SSE streaming chat — time-to-first-token optimized."""
    provider_name, unified_req, api_key = await chat_service.get_streaming_context(req, user_id)
    registry = get_registry(request)
    return create_sse_response(provider_name, unified_req, api_key, registry)


@router.websocket("/ws")
async def chat_websocket(
    ws: WebSocket,
    request: Request,
):
    """WebSocket chat — real-time bidirectional streaming."""
    # Extract token from query params for WebSocket auth
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4001, reason="Missing token")
        return

    from app.core.security import decode_token
    try:
        payload = decode_token(token)
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        await ws.close(code=4001, reason="Invalid token")
        return

    registry = get_registry(request)
    from app.api.v1.deps import get_key_repo, get_key_service
    from app.db.repositories.key_repo import KeyRepository
    from app.db.session import async_session_factory

    async with async_session_factory() as session:
        key_repo = KeyRepository(session)
        from app.services.key_service import KeyService
        key_service = KeyService(key_repo, request.app.state.redis)
        await websocket_chat(ws, user_id, registry, key_service)
