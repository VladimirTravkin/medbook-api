"""Redis-based rate limiting middleware."""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import settings
from app.core.redis import get_redis_client

# Rate limit rules: list of (method_or_None, path_prefix, (limit, period)).
# method=None means "any method"; a specific method restricts the rule.
_RATE_LIMIT_RULES: list[tuple[str | None, str, tuple[int, int]]] = []


def _parse_rate(spec: str) -> tuple[int, int]:
    """Parse a rate spec like '5/60' into (limit, period_seconds)."""
    limit_str, period_str = spec.split("/", 1)
    return int(limit_str), int(period_str)


def configure_rate_limits() -> None:
    """Populate rate limit rules from settings. Called once at startup."""
    _RATE_LIMIT_RULES.clear()

    auth_limit, auth_period = _parse_rate(settings.RATE_LIMIT_AUTH)
    _RATE_LIMIT_RULES.append((None, f"{settings.API_V1_PREFIX}/auth/", (auth_limit, auth_period)))

    appt_limit, appt_period = _parse_rate(settings.RATE_LIMIT_APPOINTMENTS)
    _RATE_LIMIT_RULES.append(
        ("POST", f"{settings.API_V1_PREFIX}/appointments", (appt_limit, appt_period))
    )


def _get_client_ip(request: Request) -> str:
    """Extract client IP, honoring X-Forwarded-For when behind a proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


def _match_rule(method: str, path: str) -> tuple[int, int] | None:
    """Return (limit, period) for the first matching rule, or None."""
    for rule_method, prefix, rule in _RATE_LIMIT_RULES:
        if rule_method is not None and rule_method != method:
            continue
        if path.startswith(prefix):
            return rule
    return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter backed by Redis.

    Uses an INCR + EXPIRE counter per (ip, path). The window resets
    when the key's TTL expires. Suitable for low-to-medium traffic APIs.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        rule = _match_rule(request.method, request.url.path)
        if rule is None:
            return await call_next(request)

        limit, period = rule
        ip = _get_client_ip(request)
        key = f"ratelimit:{ip}:{request.url.path}"

        redis = get_redis_client()
        try:
            current = await redis.incr(key)
            if current == 1:
                await redis.expire(key, period)
            ttl = await redis.ttl(key)
        except Exception:  # noqa: BLE001
            # If Redis is down, fail open (do not block traffic)
            return await call_next(request)

        if current > limit:
            retry_after = ttl if ttl > 0 else period
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Слишком много запросов, попробуйте позже",
                        "details": {"retry_after": retry_after},
                    }
                },
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        # Expose rate limit info for clients
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - current))
        return response


__all__ = ["RateLimitMiddleware", "configure_rate_limits"]
