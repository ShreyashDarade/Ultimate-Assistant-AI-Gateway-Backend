"""Conversation routes — history, threads, messages."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from starlette import status

from app.api.v1.deps import get_conv_repo, get_current_user_id, rate_limit
from app.db.repositories.conversation_repo import ConversationRepository

router = APIRouter(prefix="/conversations", tags=["conversations"], dependencies=[Depends(rate_limit)])


class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str | None = None


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    modality: str
    model_used: str | None = None
    provider_used: str | None = None
    created_at: str


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    user_id: uuid.UUID = Depends(get_current_user_id),
    conv_repo: ConversationRepository = Depends(get_conv_repo),
):
    convs = await conv_repo.list_by_user(user_id, limit, offset)
    return [
        ConversationResponse(
            id=str(c.id),
            title=c.title,
            created_at=str(c.created_at),
            updated_at=str(c.updated_at) if c.updated_at else None,
        )
        for c in convs
    ]


@router.get("/{conv_id}", response_model=dict)
async def get_conversation(
    conv_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    conv_repo: ConversationRepository = Depends(get_conv_repo),
):
    conv = await conv_repo.get_by_id(conv_id, user_id)
    if not conv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return {
        "id": str(conv.id),
        "title": conv.title,
        "created_at": str(conv.created_at),
        "messages": [
            MessageResponse(
                id=str(m.id),
                role=m.role,
                content=m.content,
                modality=m.modality,
                model_used=m.model_used,
                provider_used=m.provider_used,
                created_at=str(m.created_at),
            ).model_dump()
            for m in conv.messages
        ],
    }


@router.delete("/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conv_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    conv_repo: ConversationRepository = Depends(get_conv_repo),
):
    deleted = await conv_repo.delete(conv_id, user_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
