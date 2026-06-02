"""Aggregates all v1 route modules."""

from fastapi import APIRouter

from app.api.v1.routes import (
    admin, auth, keys, models, chat, conversions,
    images, audio, video, embeddings, files, conversations, usage,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(keys.router)
api_router.include_router(models.router)
api_router.include_router(chat.router)
api_router.include_router(conversions.router)
api_router.include_router(images.router)
api_router.include_router(audio.router)
api_router.include_router(video.router)
api_router.include_router(embeddings.router)
api_router.include_router(files.router)
api_router.include_router(conversations.router)
api_router.include_router(usage.router)
api_router.include_router(admin.router)
