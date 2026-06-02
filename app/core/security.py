"""Security — JWT, password hashing, encryption, token revocation."""

import re
import uuid
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet, MultiFernet
from jose import JWTError, jwt
from passlib.context import CryptContext
from redis.asyncio import Redis

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Password hashing ────────────────────────────────


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Password strength validation ────────────────────


def validate_password_strength(password: str) -> list[str]:
    """Return a list of issues. Empty list means the password is strong enough."""
    issues: list[str] = []
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        issues.append(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters")
    if not re.search(r"[A-Z]", password):
        issues.append("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        issues.append("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        issues.append("Password must contain at least one digit")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        issues.append("Password must contain at least one special character")
    return issues


# ── JWT ──────────────────────────────────────────────


def create_access_token(subject: str, extra: dict | None = None) -> str:
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire, "type": "access", "jti": jti}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": subject, "exp": expire, "type": "refresh", "jti": jti}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}") from e


# ── Token revocation (blacklist) ────────────────────


async def revoke_token(jti: str, ttl_seconds: int, redis: Redis) -> None:
    """Add a token's JTI to the blacklist. TTL = remaining token lifetime."""
    await redis.setex(f"revoked:{jti}", ttl_seconds, "1")


async def is_token_revoked(jti: str, redis: Redis) -> bool:
    """Check if a token has been revoked."""
    return await redis.exists(f"revoked:{jti}") > 0


# ── Account lockout ─────────────────────────────────


async def record_failed_login(email: str, redis: Redis) -> int:
    """Increment and return the failed login count for an email."""
    key = f"failed_login:{email}"
    count = await redis.incr(key)
    await redis.expire(key, settings.ACCOUNT_LOCKOUT_SECONDS)
    return count


async def is_account_locked(email: str, redis: Redis) -> bool:
    """Check if an account is locked due to too many failed login attempts."""
    key = f"failed_login:{email}"
    count = await redis.get(key)
    if count is not None and int(count) >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
        return True
    return False


async def clear_failed_logins(email: str, redis: Redis) -> None:
    """Clear the failed login counter on successful login."""
    await redis.delete(f"failed_login:{email}")


# ── Envelope encryption for BYOK keys (MultiFernet) ─


def _get_fernet() -> MultiFernet:
    """Build a MultiFernet from comma-separated keys.

    The first key is used for encryption; all keys are tried for
    decryption.  This enables zero-downtime key rotation.
    """
    raw = settings.MASTER_ENCRYPTION_KEYS
    if not raw:
        raise RuntimeError("MASTER_ENCRYPTION_KEYS is not set")
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    if not keys:
        raise RuntimeError("MASTER_ENCRYPTION_KEYS contains no valid keys")
    fernets = [Fernet(k.encode() if isinstance(k, str) else k) for k in keys]
    return MultiFernet(fernets)


def encrypt_api_key(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_api_key(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()
