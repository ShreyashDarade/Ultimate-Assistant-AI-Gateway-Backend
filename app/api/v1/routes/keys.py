"""BYOK key management routes — add, list, delete provider API keys."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from app.api.v1.deps import get_current_user_id, get_key_service, rate_limit
from app.schemas.key import AddKeyRequest, KeyResponse
from app.services.key_service import KeyService

router = APIRouter(prefix="/keys", tags=["keys"], dependencies=[Depends(rate_limit)])


@router.post("", response_model=KeyResponse, status_code=status.HTTP_201_CREATED)
async def add_key(
    req: AddKeyRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    key_service: KeyService = Depends(get_key_service),
):
    key = await key_service.add_key(user_id, req.provider, req.api_key, req.label)
    return KeyResponse(
        id=str(key.id),
        provider=key.provider,
        label=key.label,
        last4=key.last4,
        is_valid=key.is_valid,
        created_at=str(key.created_at),
    )


@router.get("", response_model=list[KeyResponse])
async def list_keys(
    user_id: uuid.UUID = Depends(get_current_user_id),
    key_service: KeyService = Depends(get_key_service),
):
    keys = await key_service.list_keys(user_id)
    return [
        KeyResponse(
            id=str(k.id),
            provider=k.provider,
            label=k.label,
            last4=k.last4,
            is_valid=k.is_valid,
            created_at=str(k.created_at),
        )
        for k in keys
    ]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(
    key_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    key_service: KeyService = Depends(get_key_service),
):
    deleted = await key_service.delete_key(key_id, user_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Key not found")
