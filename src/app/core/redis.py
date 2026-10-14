"""Redis client and cache helper functions."""

import json
from typing import Any

from redis.asyncio import Redis

from app.core.config import settings

_redis_client: Redis | None = None


def get_redis_client() -> Redis:
    """Return global Redis client, creating it lazily on first call."""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis_client() -> None:
    """Close global Redis client. Called on application shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


# ============================================
# Cache helpers
# ============================================


async def cache_get(key: str) -> Any | None:
    """Get value from cache. Returns None if key does not exist or value is invalid JSON."""
    client = get_redis_client()
    raw = await client.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def cache_set(key: str, value: Any, ttl: int) -> None:
    """Set value in cache with TTL in seconds. Value is JSON-serialized."""
    client = get_redis_client()
    await client.set(key, json.dumps(value, default=str), ex=ttl)


async def cache_delete(*keys: str) -> None:
    """Delete one or more cache keys."""
    if not keys:
        return
    client = get_redis_client()
    await client.delete(*keys)


async def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching pattern. Returns number of deleted keys.

    Uses SCAN to avoid blocking Redis with KEYS command.
    """
    client = get_redis_client()
    deleted = 0
    async for key in client.scan_iter(match=pattern, count=100):
        await client.delete(key)
        deleted += 1
    return deleted
