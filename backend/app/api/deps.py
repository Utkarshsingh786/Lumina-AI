"""
Shared FastAPI dependencies.

Why centralize deps:
- Reusable across all routers
- Single place to change auth logic
- Easy to mock in tests

Usage:
    @router.get("/me")
    async def get_me(current_user: User = Depends(get_current_user)):
        ...

    # Rate-limited endpoint (combine with auth):
    @router.post("/chat")
    async def chat(
        current_user: User = Depends(get_current_user),
        _rl: None = Depends(require_chat_rate_limit),
    ):
        ...
"""

from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.utils.rate_limit import check_rate_limit

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decode JWT and return the authenticated user.
    Raises AuthenticationError if token is invalid or user doesn't exist.
    """
    if not credentials:
        raise AuthenticationError("No authentication token provided")

    payload = decode_access_token(credentials.credentials)
    user_id = UUID(payload["sub"])

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)

    if not user or not user.is_active:
        raise AuthenticationError("User not found or inactive")

    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Returns user if authenticated, None otherwise. For public-optional endpoints."""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except Exception:
        return None


# ── Rate-limit dependencies ───────────────────────────
# Usage: add `_rl: None = Depends(require_chat_rate_limit)` to any endpoint.
# Must be used alongside get_current_user (needs user_id for the Redis key).

async def require_chat_rate_limit(
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Enforce per-user chat rate limit (streaming + regenerate endpoints).
    Limit: RATE_LIMIT_CHAT_PER_MINUTE requests per 60-second sliding window.
    """
    await check_rate_limit(
        user_id=str(current_user.id),
        limit=settings.RATE_LIMIT_CHAT_PER_MINUTE,
        window_seconds=60,
        scope="chat",
    )


async def require_api_rate_limit(
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Enforce per-user API rate limit (conversation/message write endpoints).
    Limit: RATE_LIMIT_API_PER_MINUTE requests per 60-second sliding window.
    """
    await check_rate_limit(
        user_id=str(current_user.id),
        limit=settings.RATE_LIMIT_API_PER_MINUTE,
        window_seconds=60,
        scope="api",
    )
