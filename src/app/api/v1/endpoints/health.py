"""Health check endpoint for monitoring."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Проверка работоспособности",
    description="Проверка доступности API, базы данных и Redis.",
)
async def health_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Check health of API, database and Redis.

    Returns 200 if all components are healthy, 503 otherwise.
    """
    checks: dict[str, str] = {}
    is_healthy = True

    # === Database ===
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"
        is_healthy = False

    # === Redis ===
    try:
        redis = get_redis_client()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc}"
        is_healthy = False

    payload = {
        "status": "ok" if is_healthy else "degraded",
        "checks": checks,
    }

    return JSONResponse(
        status_code=status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload,
    )
