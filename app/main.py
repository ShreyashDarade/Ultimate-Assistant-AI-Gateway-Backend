"""FastAPI app factory + middleware wiring."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from prometheus_client import make_asgi_app

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import AppException, app_exception_handler, unhandled_exception_handler
from app.core.lifespan import lifespan
from app.core.middleware import (
    PrometheusMiddleware,
    RequestIDMiddleware,
    RequestLoggingMiddleware,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.2.0",
        description="Multi-provider, any-to-any, BYOK AI assistant gateway",
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    # ── Middleware (order matters — outermost first) ──
    # 1. Request ID — outermost so every log has it.
    app.add_middleware(RequestIDMiddleware)
    # 2. Request logging — logs after response is complete.
    app.add_middleware(RequestLoggingMiddleware)
    # 3. Prometheus instrumentation.
    app.add_middleware(PrometheusMiddleware)
    # 4. CORS.
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

    # ── Prometheus metrics endpoint ──────────────────
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    # ── Routes ───────────────────────────────────────
    app.include_router(api_router)

    # ── Deep health check ────────────────────────────
    @app.get("/health")
    async def health():
        """Deep health check — pings Postgres, Redis, and reports service info."""
        import time
        from app.db.session import engine

        checks = {"service": settings.APP_NAME, "version": "0.2.0"}

        # Redis check
        try:
            redis = app.state.redis
            await redis.ping()
            checks["redis"] = "ok"
        except Exception as e:
            checks["redis"] = f"error: {e}"

        # Postgres check
        try:
            async with engine.connect() as conn:
                await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
            checks["postgres"] = "ok"
        except Exception as e:
            checks["postgres"] = f"error: {e}"

        # Provider registry
        try:
            registry = app.state.registry
            checks["providers_loaded"] = len(registry.providers)
        except Exception:
            checks["providers_loaded"] = 0

        overall = all(
            checks.get(k) == "ok" for k in ("redis", "postgres")
        )
        checks["status"] = "healthy" if overall else "degraded"

        return checks

    return app
