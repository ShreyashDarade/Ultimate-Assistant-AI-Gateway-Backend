import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation
from app.models.message import Message


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, conv_id: uuid.UUID, user_id: uuid.UUID) -> Conversation | None:
        result = await self.session.execute(
            select(Conversation)
            .where(Conversation.id == conv_id, Conversation.user_id == user_id)
            .options(selectinload(Conversation.messages))
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[Conversation]:
        result = await self.session.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc().nullsfirst(), Conversation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def create(self, user_id: uuid.UUID, title: str = "New Conversation") -> Conversation:
        conv = Conversation(user_id=user_id, title=title)
        self.session.add(conv)
        await self.session.flush()
        return conv

    async def add_message(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        modality: str = "text",
        model_used: str | None = None,
        provider_used: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            modality=modality,
            model_used=model_used,
            provider_used=provider_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        self.session.add(msg)
        await self.session.flush()
        return msg

    async def delete(self, conv_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        conv = await self.get_by_id(conv_id, user_id)
        if not conv:
            return False
        await self.session.delete(conv)
        return True
