"""Auth routes — register, login, refresh, logout."""

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette import status

from app.api.v1.deps import get_current_user_id, get_db, get_user_repo
from app.core.security import (
    clear_failed_logins,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    is_account_locked,
    is_token_revoked,
    record_failed_login,
    revoke_token,
    validate_password_strength,
    verify_password,
)
from app.db.repositories.user_repo import UserRepository
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    req: RegisterRequest,
    user_repo: UserRepository = Depends(get_user_repo),
):
    # Validate password strength
    issues = validate_password_strength(req.password)
    if issues:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": issues},
        )

    existing = await user_repo.get_by_email(req.email)
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    hashed = hash_password(req.password)
    user = await user_repo.create(req.email, hashed)

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    request: Request,
    user_repo: UserRepository = Depends(get_user_repo),
):
    redis = request.app.state.redis

    # Check account lockout
    if await is_account_locked(req.email, redis):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Account temporarily locked due to too many failed login attempts. Try again later.",
        )

    user = await user_repo.get_by_email(req.email)
    if not user or not verify_password(req.password, user.hashed_password):
        if user:
            await record_failed_login(req.email, redis)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")

    # Clear failed attempts on successful login
    await clear_failed_logins(req.email, redis)

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, request: Request):
    redis = request.app.state.redis
    try:
        payload = decode_token(req.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")

        jti = payload.get("jti")
        if jti and await is_token_revoked(jti, redis):
            raise ValueError("Token has been revoked")

        user_id = payload["sub"]
    except (ValueError, KeyError) as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token") from e

    # Revoke the old refresh token so it cannot be reused (rotation).
    if jti:
        remaining_ttl = max(int(payload["exp"] - __import__("time").time()), 1)
        await revoke_token(jti, remaining_ttl, redis)

    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    user_id=Depends(get_current_user_id),
):
    """Revoke the current access token so it can no longer be used."""
    redis = request.app.state.redis
    # Re-decode the token from the Authorization header to get the jti.
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    try:
        payload = decode_token(token)
        jti = payload.get("jti")
        if jti:
            remaining_ttl = max(int(payload["exp"] - __import__("time").time()), 1)
            await revoke_token(jti, remaining_ttl, redis)
    except ValueError:
        pass  # Token already expired or invalid — nothing to revoke
