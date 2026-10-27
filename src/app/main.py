"""FastAPI application entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints import health
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.rate_limit import RateLimitMiddleware, configure_rate_limits
from app.core.redis import close_redis_client, get_redis_client


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: warm up Redis on startup, close on shutdown."""
    # Startup: initialise Redis client eagerly and load rate limits
    get_redis_client()
    configure_rate_limits()
    yield
    # Shutdown: close Redis connection
    await close_redis_client()


API_DESCRIPTION = """
REST API для записи на приём в клинику.

## 🚀 Быстрый старт

1. Откройте **`POST /api/v1/auth/login`** → **Try it out** → **Execute** с демо-данными:
   - **Email:** `demo@example.com`
   - **Пароль:** `demopassword123`
2. Скопируйте `access_token` из ответа.
3. Нажмите кнопку **Authorize** (вверху страницы) → вставьте токен в поле **Value** → **Authorize**.
4. Теперь эндпоинты с иконкой 🔒 доступны для запросов.

## 🩺 Что можно попробовать

- **`GET /api/v1/doctors`** — каталог врачей
- **`GET /api/v1/doctors/{doctor_id}/slots?only_free=true`** — свободные слоты врача
- **`POST /api/v1/appointments`** — записаться на приём
- **`GET /api/v1/appointments`** — свои записи

## 📚 Документация

- **README:** [github.com/VladimirTravkin/medbook-api](https://github.com/VladimirTravkin/medbook-api)
- **Архитектура:** [`docs/ARCHITECTURE.ru.md`](https://github.com/VladimirTravkin/medbook-api/blob/main/docs/ARCHITECTURE.ru.md)
"""

API_TAGS_METADATA = [
    {"name": "health", "description": "Проверка работоспособности API, базы данных и Redis."},
    {"name": "auth", "description": "Регистрация, вход, обновление токенов и выход из системы."},
    {"name": "users", "description": "Профиль текущего пользователя."},
    {"name": "specializations", "description": "Справочник медицинских специализаций."},
    {"name": "doctors", "description": "Каталог врачей и управление профилями."},
    {"name": "slots", "description": "Расписание врачей: слоты для записи."},
    {"name": "appointments", "description": "Записи на приём: бронирование, отмена, статусы."},
]


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        description=API_DESCRIPTION,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=API_TAGS_METADATA,
        swagger_ui_parameters={"persistAuthorization": True},
        lifespan=lifespan,
    )

    # === CORS ===
    # Only the methods and headers we actually expose.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
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
