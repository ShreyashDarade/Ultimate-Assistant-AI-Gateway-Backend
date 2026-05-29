"""FastAPI app factory + middleware wiring."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import AppException, app_exception_handler, unhandled_exception_handler
from app.core.lifespan import lifespan


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="Multi-provider, any-to-any, BYOK AI assistant gateway",
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    # ── CORS ─────────────────────────────────────────
    allow_origins = ["*"] if settings.DEBUG else settings.cors_origins_list
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        # Credentials cannot be combined with the wildcard origin per the spec.
        allow_credentials=allow_origins != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers ───────────────────────────
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # ── Routes ───────────────────────────────────────
    app.include_router(api_router)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": settings.APP_NAME}

    return app
