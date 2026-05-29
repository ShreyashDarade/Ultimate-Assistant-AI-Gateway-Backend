"""Auth routes — register, login, refresh."""

from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from app.api.v1.deps import get_db, get_user_repo
from app.core.security import (
    create_access_token, create_refresh_token,
    decode_token, hash_password, verify_password,
)
from app.db.repositories.user_repo import UserRepository
from app.schemas.auth import (
    LoginRequest, RefreshRequest, RegisterRequest,
    TokenResponse, UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    req: RegisterRequest,
    user_repo: UserRepository = Depends(get_user_repo),
):
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
    user_repo: UserRepository = Depends(get_user_repo),
):
    user = await user_repo.get_by_email(req.email)
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest):
    try:
        payload = decode_token(req.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
        user_id = payload["sub"]
    except (ValueError, KeyError) as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token") from e

    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )
