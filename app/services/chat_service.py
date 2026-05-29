"""Chat service — orchestrates chat requests, history, streaming."""

import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.repositories.conversation_repo import ConversationRepository
from app.providers.base import ChatCapable
from app.providers.registry import ProviderRegistry
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.provider import UnifiedRequest
from app.services.key_service import KeyService
from app.services.router import ModalityRouter

logger = get_logger(__name__)


class ChatService:
    def __init__(
        self,
        router: ModalityRouter,
        registry: ProviderRegistry,
        key_service: KeyService,
        session: AsyncSession,
    ):
        self.router = router
        self.registry = registry
        self.key_service = key_service
        self.conv_repo = ConversationRepository(session)

    async def chat(self, req: ChatRequest, user_id: uuid.UUID) -> ChatResponse:
        start = time.monotonic()

        # Create/get conversation
        conv_id = uuid.UUID(req.conversation_id) if req.conversation_id else None
        if not conv_id:
            conv = await self.conv_repo.create(user_id)
            conv_id = conv.id

        # Store user message
        user_msg = req.messages[-1] if req.messages else None
        if user_msg:
            await self.conv_repo.add_message(conv_id, user_msg.role, user_msg.content)

        # Route to provider
        unified_req = UnifiedRequest(
            messages=[{"role": m.role, "content": m.content} for m in req.messages],
            model=req.model,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
        result = await self.router.route(
            unified_req, user_id, "text", "text",
            preferred_provider=req.provider,
            preferred_model=req.model,
        )

        elapsed_ms = int((time.monotonic() - start) * 1000)

        # Store assistant message
        await self.conv_repo.add_message(
            conv_id, "assistant", result.content or "",
            model_used=result.model,
            provider_used=result.provider,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )

        return ChatResponse(
            id=str(conv_id),
            content=result.content or "",
            model=result.model or "",
            provider=result.provider or "",
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=elapsed_ms,
        )

    async def get_streaming_context(
        self, req: ChatRequest, user_id: uuid.UUID
    ) -> tuple[str, UnifiedRequest, str]:
        """Prepare context for SSE streaming — returns (provider_name, unified_req, api_key)."""
        # Determine provider + model
        capable = self.registry.get_capable_providers("text", "text")
        user_providers = await self.key_service.get_user_providers(user_id)
        available = [(p, m) for p, m in capable if p in user_providers]

        if req.provider:
            available = [(p, m) for p, m in available if p == req.provider] or available
        if req.model:
            available = [(p, m) for p, m in available if m == req.model] or available

        provider_name, model_id = available[0]
        api_key = await self.key_service.get_decrypted_key(user_id, provider_name)

        unified_req = UnifiedRequest(
            messages=[{"role": m.role, "content": m.content} for m in req.messages],
            model=req.model or model_id,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            stream=True,
        )
        return provider_name, unified_req, api_key
