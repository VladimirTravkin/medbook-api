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

## 🔑 Шаг 0 — Авторизация (обязательно для защищённых эндпоинтов)

**Для чтения каталога (врачи, специализации, слоты) авторизация НЕ нужна.**

Для записи на приём, просмотра своих записей и управления — нужно войти:

1. Откройте **`POST /api/v1/auth/login`** → **Try it out** → вставьте:
   ```json
   {"email": "demo@example.com", "password": "demopassword123"}
   ```
2. Нажмите **Execute** → скопируйте **`access_token`** из ответа (длинная строка `eyJ...`).
3. Нажмите **Authorize** (вверху страницы) → вставьте токен в поле **Value** → **Authorize** → **Close**.
4. Теперь эндпоинты с иконкой 🔒 доступны.

> Токен живёт 60 минут. Если истёк — повторите шаг 1.

---

## 🩺 Шаг 1 — Посмотреть каталог врачей

1. **`GET /api/v1/doctors`** → **Try it out** → **Execute**.
2. В ответе вы увидите список врачей. Каждый содержит `id` (это **`doctor_id`**), `full_name`, `specialization`.
3. **Скопируйте `id` любого врача** — он понадобится в шаге 2.

---

## 📅 Шаг 2 — Посмотреть свободные слоты врача

1. **`GET /api/v1/doctors/{doctor_id}/slots`** → **Try it out**.
2. В поле **`doctor_id`** вставьте `id` из шага 1 (не перепутайте с `user_id`!).
3. В поле **`only_free`** выберите `true` — покажет только свободные слоты.
4. **Execute** → в ответе будет список слотов. Каждый содержит `id` (это **`slot_id`**).
5. **Скопируйте `id` любого слота** — он понадобится в шаге 3.

> Не путайте `doctor_id` (id врача) и `slot_id` (id слота). Это разные UUID. `doctor_id` берётся из `GET /doctors`, `slot_id` — из `GET /doctors/{id}/slots`.

---

## 📝 Шаг 3 — Записаться на приём

1. Убедитесь, что вы авторизованы под пациентом (см. «Шаг 0»).
2. **`POST /api/v1/appointments`** → **Try it out**.
3. В Request body вставьте:
   ```json
   {"slot_id": "ВСТАВЬТЕ_СЮДА_id_слота_из_шага_2", "notes": "Первичный приём"}
   ```
4. **Execute** → ожидаемый ответ: **`201 Created`** с полными данными записи.

---

## 📋 Шаг 4 — Посмотреть свои записи

1. **`GET /api/v1/appointments`** → **Try it out** → **Execute**.
2. Вы увидите список своих записей со статусами (`pending`, `confirmed`, `cancelled`, `completed`, `no_show`).

**Отмена записи:** **`POST /api/v1/appointments/{appointment_id}/cancel`** → скопируйте `id` из шага 4 → **Try it out** → **Execute**.

---

## 🩺 Что ещё можно попробовать (требуется роль admin или doctor)

Эти эндпоинты требуют другой роли. Обычный демо-пользователь их не выполнит — они описаны для полноты API.

- **`POST /api/v1/specializations`** — создать специализацию (admin).
- **`POST /api/v1/doctors`** — создать врача (admin).
- **`POST /api/v1/doctors/{id}/slots/generate`** — сгенерировать слоты на неделю (doctor/admin).
- **`PATCH /api/v1/appointments/{id}/status`** — изменить статус записи (doctor/admin).

---

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
