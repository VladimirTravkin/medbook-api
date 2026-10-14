"""FastAPI application entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints import health
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.redis import close_redis_client, get_redis_client
from app.core.rate_limit import RateLimitMiddleware, configure_rate_limits


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: warm up Redis on startup, close on shutdown."""
    # Startup: initialise Redis client eagerly and load rate limits
    get_redis_client()
    configure_rate_limits()
    yield
    # Shutdown: close Redis connection
    await close_redis_client()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        description="REST API для записи на приём в клинику",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # === CORS ===
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # === Rate limiting ===
    app.add_middleware(RateLimitMiddleware)

    # === Exception handlers ===
    register_exception_handlers(app)

    # === Routers ===
    app.include_router(health.router)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
