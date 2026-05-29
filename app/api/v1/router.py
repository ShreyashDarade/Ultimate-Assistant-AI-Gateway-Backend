"""Aggregates all v1 route modules."""

from fastapi import APIRouter

from app.api.v1.routes import (
    auth, keys, models, chat, conversions,
    images, audio, video, embeddings, files, conversations,
)

api_router = APIRouter(prefix="/v1")

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
