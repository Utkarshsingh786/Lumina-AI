"""
Redis sliding-window rate limiter.

Algorithm: sorted set per (user, scope), scored by request timestamp.
On each request:
  1. Remove entries older than the window (ZREMRANGEBYSCORE)
  2. Count remaining entries (ZCARD)
  3. Add this request's timestamp (ZADD)
  4. Set TTL to auto-clean the key (EXPIRE)
  5. If count (before this add) >= limit → raise RateLimitError

Why sorted set instead of a simple counter:
- Counter resets hard at window boundaries → burst at the boundary edge
- Sorted set tracks exact timestamps → true sliding window, no burst exploit

Why pipeline (not Lua):
- A single extra request may slip through under heavy concurrency, but
  the window self-corrects in the next tick. Acceptable for chat rate limits.
- Lua adds deployment complexity and is overkill for this use-case.

Key naming:  rate:{user_id}:{scope}
"""

import time

from app.core.exceptions import RateLimitError
from app.core.logging import get_logger
from app.utils.cache import get_redis

logger = get_logger(__name__)

# Key TTL is slightly longer than the window so Redis auto-cleans idle keys
_KEY_TTL_BUFFER_S = 10


async def check_rate_limit(
    user_id: str,
    limit: int,
    window_seconds: int = 60,
    scope: str = "api",
) -> None:
    """
    Enforce a sliding-window rate limit for a user.

    Raises RateLimitError (HTTP 429) if the user has exceeded `limit`
    requests within the last `window_seconds` seconds.

    Args:
        user_id:        User identifier string.
        limit:          Maximum allowed requests in the window.
        window_seconds: Length of the sliding window.
        scope:          Differentiates multiple limits per user (chat vs api).
    """
    key = f"rate:{user_id}:{scope}"
    now_ms = int(time.time() * 1000)
    window_start_ms = now_ms - (window_seconds * 1000)

    try:
        redis = await get_redis()

        # Pipeline: remove stale entries, count, add current, refresh TTL
        async with redis.pipeline(transaction=False) as pipe:
            pipe.zremrangebyscore(key, "-inf", window_start_ms)
            pipe.zcard(key)
            pipe.zadd(key, {str(now_ms): now_ms})
            pipe.expire(key, window_seconds + _KEY_TTL_BUFFER_S)
            results = await pipe.execute()

        count_before_this_request: int = results[1]

        if count_before_this_request >= limit:
            # Compute when the oldest request in the window falls out
            oldest_score = await redis.zrange(key, 0, 0, withscores=True)
            if oldest_score:
                oldest_ms = int(oldest_score[0][1])
                retry_after = max(1, window_seconds - (now_ms - oldest_ms) // 1000)
            else:
                retry_after = window_seconds

            logger.warning(
                "rate_limit.exceeded",
                user_id=user_id,
                scope=scope,
                count=count_before_this_request,
                limit=limit,
                retry_after=retry_after,
            )
            raise RateLimitError(
                message=f"Rate limit exceeded. Try again in {retry_after}s.",
                details={"retry_after": retry_after, "limit": limit, "window": window_seconds},
            )

    except RateLimitError:
        raise
    except Exception as e:
        # Redis failure must never block the user — fail open
        logger.warning("rate_limit.redis_error", error=str(e), user_id=user_id)
