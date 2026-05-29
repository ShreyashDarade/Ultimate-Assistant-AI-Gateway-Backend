"""Models route — list available models and capabilities."""

from fastapi import APIRouter, Depends, Request

from app.api.v1.deps import get_current_user_id, get_registry, rate_limit
from app.providers.registry import ProviderRegistry
from app.schemas.provider import ModelInfo, ProviderInfo

router = APIRouter(prefix="/models", tags=["models"], dependencies=[Depends(rate_limit)])


@router.get("", response_model=list[ModelInfo])
async def list_models(
    request: Request,
    _user_id=Depends(get_current_user_id),
):
    registry: ProviderRegistry = get_registry(request)
    models = []
    for provider in registry.providers.values():
        models.extend(provider.get_models())
    return models


@router.get("/providers", response_model=list[ProviderInfo])
async def list_providers(
    request: Request,
    _user_id=Depends(get_current_user_id),
):
    registry: ProviderRegistry = get_registry(request)
    providers = []
    for name, adapter in registry.providers.items():
        caps = adapter.get_capabilities()
        cap_strs = [f"{k[0].value}→{k[1].value}" for k in caps.keys()]
        models = adapter.get_models()
        providers.append(ProviderInfo(name=name, models=models, capabilities=cap_strs))
    return providers


@router.get("/capabilities")
async def list_capabilities(
    request: Request,
    _user_id=Depends(get_current_user_id),
):
    registry: ProviderRegistry = get_registry(request)
    result = {}
    for (in_mod, out_mod), pairs in registry.capability_map.items():
        key = f"{in_mod.value}→{out_mod.value}"
        result[key] = [{"provider": p, "model": m} for p, m in pairs]
    return result
