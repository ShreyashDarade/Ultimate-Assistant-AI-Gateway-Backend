import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey


class KeyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, key_id: uuid.UUID) -> ApiKey | None:
        return await self.session.get(ApiKey, key_id)

    async def list_by_user(self, user_id: uuid.UUID) -> list[ApiKey]:
        result = await self.session.execute(
            select(ApiKey).where(ApiKey.user_id == user_id).order_by(ApiKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_user_and_provider(self, user_id: uuid.UUID, provider: str) -> ApiKey | None:
        result = await self.session.execute(
            select(ApiKey).where(ApiKey.user_id == user_id, ApiKey.provider == provider, ApiKey.is_valid == True)
        )
        return result.scalar_one_or_none()

    async def create(self, user_id: uuid.UUID, provider: str, encrypted_key: str, last4: str, label: str = "default") -> ApiKey:
        key = ApiKey(
            user_id=user_id,
            provider=provider,
            encrypted_key=encrypted_key,
            last4=last4,
            label=label,
        )
        self.session.add(key)
        await self.session.flush()
        return key

    async def delete_key(self, key_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            delete(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id)
        )
        return result.rowcount > 0

    async def get_user_providers(self, user_id: uuid.UUID) -> list[str]:
        result = await self.session.execute(
            select(ApiKey.provider).where(ApiKey.user_id == user_id, ApiKey.is_valid == True).distinct()
        )
        return list(result.scalars().all())
