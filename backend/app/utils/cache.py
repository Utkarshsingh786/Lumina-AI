"""
Redis cache utilities.

Patterns:
- get_redis(): connection pool singleton (reused across requests)
- cache_get/cache_set: typed JSON cache
- invalidate_pattern: bulk invalidation for cache busting

What to cache:
- Conversation list (per user) — invalidate on create/delete/update
- User settings — invalidate on profile update
- Memory entries (per user) — invalidate on memory extraction
- NOT: individual messages (too granular, freshness matters)
- NOT: streaming responses (impossible by nature)

TTL strategy:
- Short (60s): things that change frequently (conversation list)
- Medium (5m): user settings
- Long (1h): rarely-changing data (personas, model list)
"""

import json
from functools import lru_cache
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Get a Redis connection from the pool. Lazily initialized."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis_pool


async def cache_get(key: str) -> Any | None:
    """Get a JSON-deserialized value from cache. Returns None on miss."""
    try:
        redis = await get_redis()
        value = await redis.get(key)
        if value is None:
            return None
        return json.loads(value)
    except Exception as e:
        logger.warning("cache.get_error", key=key, error=str(e))
        return None


async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    """JSON-serialize and store a value in cache."""
    try:
        redis = await get_redis()
        serialized = json.dumps(value, default=str)
        await redis.set(key, serialized, ex=ttl or settings.REDIS_CACHE_TTL)
    except Exception as e:
        logger.warning("cache.set_error", key=key, error=str(e))


async def cache_delete(key: str) -> None:
    """Delete a cache key."""
    try:
        redis = await get_redis()
        await redis.delete(key)
    except Exception as e:
        logger.warning("cache.delete_error", key=key, error=str(e))


async def invalidate_pattern(pattern: str) -> int:
    """
    Delete all keys matching a pattern.
    Use sparingly — SCAN is O(N) over all keys.
    Better: use structured key naming and delete exact keys.
    """
    try:
        redis = await get_redis()
        keys = [key async for key in redis.scan_iter(pattern)]
        if keys:
            await redis.delete(*keys)
        return len(keys)
    except Exception as e:
        logger.warning("cache.invalidate_error", pattern=pattern, error=str(e))
        return 0


# ── Cache Key Helpers ─────────────────────────────────
# Centralized key naming prevents typos and makes invalidation easy.

def user_conversations_key(user_id: str) -> str:
    return f"user:{user_id}:conversations"

def user_memory_key(user_id: str) -> str:
    return f"user:{user_id}:memory"

def user_settings_key(user_id: str) -> str:
    return f"user:{user_id}:settings"
