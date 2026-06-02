"""BYOK key service — encrypt/decrypt/cache provider API keys.

This is the ONLY place that decrypts user keys. Never store decrypted keys
in the database. Decrypted keys are cached **in-process only** with a short
TTL — they never leave the process boundary (no Redis, no disk).
"""

import uuid

import cachetools
from redis.asyncio import Redis

from app.core.logging import get_logger
from app.core.security import decrypt_api_key, encrypt_api_key
from app.db.repositories.key_repo import KeyRepository

logger = get_logger(__name__)

# In-process TTL cache for decrypted keys.
# Keyed by "user_id:provider" → plaintext key.
# Max 2000 entries, each lives for 60 seconds.
_decrypted_key_cache: cachetools.TTLCache[str, str] = cachetools.TTLCache(
    maxsize=2000, ttl=60
)


class KeyService:
    def __init__(self, key_repo: KeyRepository, redis: Redis):
        self.key_repo = key_repo
        self.redis = redis  # kept for invalidation signaling, not for storing secrets

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
        # Invalidate in-process cache for this user+provider.
        _decrypted_key_cache.pop(f"{user_id}:{provider}", None)
        logger.info("key_added", user_id=str(user_id), provider=provider, key_id=str(key_record.id))
        return key_record

    async def list_keys(self, user_id: uuid.UUID):
        return await self.key_repo.list_by_user(user_id)

    async def delete_key(self, key_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        # Invalidate all cached keys for this user.
        self._invalidate_user_cache(user_id)
        result = await self.key_repo.delete_key(key_id, user_id)
        if result:
            logger.info("key_deleted", user_id=str(user_id), key_id=str(key_id))
        return result

    def _invalidate_user_cache(self, user_id: uuid.UUID) -> None:
        """Remove all cached keys for a given user from the in-process cache."""
        prefix = f"{user_id}:"
        keys_to_remove = [k for k in _decrypted_key_cache if k.startswith(prefix)]
        for k in keys_to_remove:
            _decrypted_key_cache.pop(k, None)

    async def get_decrypted_key(self, user_id: uuid.UUID, provider: str) -> str:
        cache_key = f"{user_id}:{provider}"

        # Check in-process cache first.
        cached = _decrypted_key_cache.get(cache_key)
        if cached is not None:
            return cached

        # Load from DB and decrypt.
        key_record = await self.key_repo.get_by_user_and_provider(user_id, provider)
        if not key_record:
            from app.core.exceptions import ProviderKeyMissing
            raise ProviderKeyMissing(provider)

        decrypted = decrypt_api_key(key_record.encrypted_key)

        # Cache in-process only (never serialized anywhere).
        _decrypted_key_cache[cache_key] = decrypted
        logger.debug("key_decrypted", user_id=str(user_id), provider=provider)
        return decrypted

    async def get_user_providers(self, user_id: uuid.UUID) -> list[str]:
        return await self.key_repo.get_user_providers(user_id)
