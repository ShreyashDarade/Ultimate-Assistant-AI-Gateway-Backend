"""Admin routes — user management, provider health, system stats.

All endpoints require the user to have role='admin'.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from starlette import status

from app.api.v1.deps import get_current_user_id, get_db, get_registry
from app.db.repositories.user_repo import UserRepository
from app.providers.registry import ProviderRegistry

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Admin guard ──────────────────────────────────────

async def require_admin(
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Dependency that ensures the caller has admin role."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.db.session import async_session_factory

    async with async_session_factory() as session:
        repo = UserRepository(session)
        user = await repo.get_by_id(user_id)
        if not user or getattr(user, "role", "user") != "admin":
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Admin access required",
            )
    return user_id


# ── Schemas ──────────────────────────────────────────

class AdminUserResponse(BaseModel):
    id: str
    email: str
    role: str
    tier: str
    is_active: bool
    created_at: str


class ProviderHealthResponse(BaseModel):
    name: str
    status: str  # healthy / degraded / unavailable
    models_count: int
    capabilities: list[str]


class SystemStatsResponse(BaseModel):
    total_providers: int
    total_models: int
    total_capabilities: int


# ── Endpoints ────────────────────────────────────────

@router.get("/users", response_model=list[AdminUserResponse], dependencies=[Depends(require_admin)])
async def list_users(
    limit: int = 50,
    offset: int = 0,
    request: Request = None,
):
    """List all users with their roles and tiers."""
    from sqlalchemy import select
    from app.db.session import async_session_factory
    from app.models.user import User

    async with async_session_factory() as session:
        result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
        )
        users = result.scalars().all()
        return [
            AdminUserResponse(
                id=str(u.id),
                email=u.email,
                role=getattr(u, "role", "user"),
                tier=getattr(u, "tier", "free"),
                is_active=u.is_active,
                created_at=str(u.created_at),
            )
            for u in users
        ]


@router.get("/providers/health", response_model=list[ProviderHealthResponse], dependencies=[Depends(require_admin)])
async def provider_health(request: Request):
    """Real-time health of all loaded providers."""
    registry: ProviderRegistry = get_registry(request)
    results = []
    for name, adapter in registry.providers.items():
        caps = adapter.get_capabilities()
        cap_strs = [f"{k[0].value}→{k[1].value}" for k in caps.keys()]
        models_count = len(adapter.get_models())

        # Check circuit breaker state
        from app.providers.retry import circuit_breaker
        is_open = await circuit_breaker.is_open(name)
        cb_status = "unavailable" if is_open else "healthy"

        results.append(ProviderHealthResponse(
            name=name,
            status=cb_status,
            models_count=models_count,
            capabilities=cap_strs,
        ))
    return results


@router.post("/providers/{provider_name}/disable", dependencies=[Depends(require_admin)])
async def disable_provider(provider_name: str, request: Request):
    """Manually open the circuit breaker for a provider."""
    from app.providers.retry import circuit_breaker
    await circuit_breaker.record_failure(provider_name)
    # Force open by recording enough failures
    for _ in range(circuit_breaker.failure_threshold):
        await circuit_breaker.record_failure(provider_name)
    return {"status": "disabled", "provider": provider_name}


@router.post("/providers/{provider_name}/enable", dependencies=[Depends(require_admin)])
async def enable_provider(provider_name: str, request: Request):
    """Manually close the circuit breaker for a provider."""
    from app.providers.retry import circuit_breaker
    await circuit_breaker.record_success(provider_name)
    return {"status": "enabled", "provider": provider_name}


@router.get("/stats", response_model=SystemStatsResponse, dependencies=[Depends(require_admin)])
async def system_stats(request: Request):
    """System-wide metrics."""
    registry: ProviderRegistry = get_registry(request)
    total_models = sum(len(a.get_models()) for a in registry.providers.values())
    total_caps = len(registry.capability_map)
    return SystemStatsResponse(
        total_providers=len(registry.providers),
        total_models=total_models,
        total_capabilities=total_caps,
    )
