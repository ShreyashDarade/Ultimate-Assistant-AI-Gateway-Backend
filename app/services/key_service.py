"""BYOK key service — encrypt/decrypt/cache provider API keys.

This is the ONLY place that decrypts user keys. Never store decrypted keys
in the database. Optionally cache decrypted keys in memory with short TTL.
"""

import uuid

from redis.asyncio import Redis

from app.core.logging import get_logger
from app.core.security import decrypt_api_key, encrypt_api_key
from app.db.repositories.key_repo import KeyRepository

logger = get_logger(__name__)

DECRYPTED_KEY_TTL = 60  # short-lived in-Redis cache for decrypted keys (seconds)


class KeyService:
    def __init__(self, key_repo: KeyRepository, redis: Redis):
        self.key_repo = key_repo
        self.redis = redis

    async def add_key(self, user_id: uuid.UUID, provider: str, api_key: str, label: str = "default"):
        encrypted = encrypt_api_key(api_key)
        last4 = api_key[-4:]
        key_record = await self.key_repo.create(
            user_id=user_id,
            provider=provider,
            encrypted_key=encrypted,
            last4=last4,
            label=label,
        )
        # Invalidate any stale decrypted-key cache for this provider.
        await self.redis.delete(f"dk:{user_id}:{provider}")
        logger.info("key_added", user_id=str(user_id), provider=provider, key_id=str(key_record.id))
        return key_record

    async def list_keys(self, user_id: uuid.UUID):
        return await self.key_repo.list_by_user(user_id)

    async def delete_key(self, key_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        # Invalidate cache. Redis DELETE does not expand glob patterns, so we
        # scan for matching keys and delete them in batches.
        await self._invalidate_user_cache(user_id)
        result = await self.key_repo.delete_key(key_id, user_id)
        if result:
            logger.info("key_deleted", user_id=str(user_id), key_id=str(key_id))
        return result

    async def _invalidate_user_cache(self, user_id: uuid.UUID) -> None:
        pattern = f"dk:{user_id}:*"
        async for cache_key in self.redis.scan_iter(match=pattern, count=100):
            await self.redis.delete(cache_key)

    async def get_decrypted_key(self, user_id: uuid.UUID, provider: str) -> str:
        # Check cache first
        cache_key = f"dk:{user_id}:{provider}"
        cached = await self.redis.get(cache_key)
        if cached:
            return cached

        # Load from DB and decrypt
        key_record = await self.key_repo.get_by_user_and_provider(user_id, provider)
        if not key_record:
            from app.core.exceptions import ProviderKeyMissing
            raise ProviderKeyMissing(provider)

        decrypted = decrypt_api_key(key_record.encrypted_key)

        # Cache briefly (never persist decrypted)
        await self.redis.setex(cache_key, DECRYPTED_KEY_TTL, decrypted)
        logger.debug("key_decrypted", user_id=str(user_id), provider=provider)
        return decrypted

    async def get_user_providers(self, user_id: uuid.UUID) -> list[str]:
        return await self.key_repo.get_user_providers(user_id)
