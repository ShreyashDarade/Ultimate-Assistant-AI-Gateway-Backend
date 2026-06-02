"""Chat service — orchestrates chat requests, history, caching, guardrails, and streaming."""

import time
import uuid

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.telemetry import CACHE_OPERATIONS, ESTIMATED_COST, TOKENS_USED
from app.db.repositories.conversation_repo import ConversationRepository
from app.providers.base import ChatCapable
from app.providers.registry import ProviderRegistry
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.provider import UnifiedRequest
from app.services.cache import ResponseCache
from app.services.cost_service import CostService
from app.services.guardrails import Guardrails
from app.services.key_service import KeyService
from app.services.router import ModalityRouter
from app.services.usage_service import UsageService
from app.utils.tokens import estimate_cost

logger = get_logger(__name__)


class ChatService:
    def __init__(
        self,
        router: ModalityRouter,
        registry: ProviderRegistry,
        key_service: KeyService,
        session: AsyncSession,
        redis: Redis,
    ):
        self.router = router
        self.registry = registry
        self.key_service = key_service
        self.conv_repo = ConversationRepository(session)
        self.cache = ResponseCache(redis)
        self.usage_service = UsageService(session)

    async def chat(self, req: ChatRequest, user_id: uuid.UUID) -> ChatResponse:
        start = time.monotonic()

        # ── 1. Guardrails pre-check ──────────────────
        last_message = req.messages[-1] if req.messages else None
        if last_message and last_message.content:
            text_content = (
                last_message.content
                if isinstance(last_message.content, str)
                else " ".join(p.text or "" for p in last_message.content if hasattr(p, "text"))
            )
            guard_result = Guardrails.pre_check(text_content, tier="free")
            if guard_result.blocked:
                from app.core.exceptions import AppException
                raise AppException(
                    status_code=422,
                    detail="; ".join(guard_result.warnings),
                )

        # ── 2. Build messages for cache key + provider ──
        messages_for_hash = []
        for m in req.messages:
            content = m.content if isinstance(m.content, str) else str(m.content)
            messages_for_hash.append({"role": m.role, "content": content})

        # ── 3. Check cache (only for non-streaming, deterministic requests) ──
        is_cacheable = not req.stream and req.temperature == 0 and not req.bypass_cache
        if is_cacheable:
            cached = await self.cache.get(
                user_id=str(user_id),
                provider=req.provider or "",
                model=req.model or "",
                messages=messages_for_hash,
                temperature=req.temperature,
            )
            if cached:
                CACHE_OPERATIONS.labels(operation="hit").inc()
                elapsed_ms = int((time.monotonic() - start) * 1000)
                return ChatResponse(
                    id=cached.get("conversation_id", str(uuid.uuid4())),
                    content=cached.get("content", ""),
                    model=cached.get("model", ""),
                    provider=cached.get("provider", ""),
                    input_tokens=cached.get("input_tokens"),
                    output_tokens=cached.get("output_tokens"),
                    latency_ms=elapsed_ms,
                    estimated_cost_usd=cached.get("estimated_cost_usd"),
                    cached=True,
                )
            CACHE_OPERATIONS.labels(operation="miss").inc()

        # ── 4. Create/get conversation ───────────────
        conv_id = uuid.UUID(req.conversation_id) if req.conversation_id else None
        if not conv_id:
            conv = await self.conv_repo.create(user_id)
            conv_id = conv.id

        # Store user message
        if last_message:
            content_str = (
                last_message.content
                if isinstance(last_message.content, str)
                else str(last_message.content)
            )
            await self.conv_repo.add_message(conv_id, last_message.role, content_str)

        # ── 5. Route to provider ─────────────────────
        unified_req = UnifiedRequest(
            messages=messages_for_hash,
            model=req.model,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            tools=[t.model_dump() for t in req.tools] if req.tools else None,
            tool_choice=req.tool_choice,
        )
        result = await self.router.route(
            unified_req, user_id, "text", "text",
            preferred_provider=req.provider,
            preferred_model=req.model,
        )

        elapsed_ms = int((time.monotonic() - start) * 1000)

        # ── 6. Guardrails post-check ─────────────────
        if result.content:
            post_guard = Guardrails.post_check(result.content)
            if post_guard.warnings:
                logger.warning("guardrail_post_warning", warnings=post_guard.warnings)

        # ── 7. Cost estimation ───────────────────────
        cost_usd = None
        if result.input_tokens and result.output_tokens:
            cost_usd = float(CostService.estimate(
                result.provider or "", result.model or "",
                result.input_tokens, result.output_tokens,
            ))
            TOKENS_USED.labels(
                provider=result.provider or "", model=result.model or "", direction="input"
            ).inc(result.input_tokens)
            TOKENS_USED.labels(
                provider=result.provider or "", model=result.model or "", direction="output"
            ).inc(result.output_tokens)
            ESTIMATED_COST.labels(
                provider=result.provider or "", model=result.model or "",
            ).inc(cost_usd)

        # ── 8. Record usage ──────────────────────────
        await self.usage_service.record(
            user_id=user_id,
            provider=result.provider or "",
            model=result.model or "",
            input_tokens=result.input_tokens or 0,
            output_tokens=result.output_tokens or 0,
            latency_ms=elapsed_ms,
        )

        # ── 9. Store assistant message ───────────────
        await self.conv_repo.add_message(
            conv_id, "assistant", result.content or "",
            model_used=result.model,
            provider_used=result.provider,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )

        # ── 10. Cache response ───────────────────────
        response = ChatResponse(
            id=str(conv_id),
            content=result.content or "",
            model=result.model or "",
            provider=result.provider or "",
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=elapsed_ms,
            estimated_cost_usd=cost_usd,
            tool_calls=result.tool_calls,
        )

        if is_cacheable and result.content:
            await self.cache.set(
                user_id=str(user_id),
                provider=result.provider or "",
                model=result.model or "",
                messages=messages_for_hash,
                temperature=req.temperature,
                response={
                    "conversation_id": str(conv_id),
                    "content": result.content,
                    "model": result.model,
                    "provider": result.provider,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "estimated_cost_usd": cost_usd,
                },
            )

        return response

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

        messages_for_provider = []
        for m in req.messages:
            content = m.content if isinstance(m.content, str) else str(m.content)
            messages_for_provider.append({"role": m.role, "content": content})

        unified_req = UnifiedRequest(
            messages=messages_for_provider,
            model=req.model or model_id,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            stream=True,
            tools=[t.model_dump() for t in req.tools] if req.tools else None,
            tool_choice=req.tool_choice,
        )
        return provider_name, unified_req, api_key
