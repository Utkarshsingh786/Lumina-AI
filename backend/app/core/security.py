"""
Security utilities: password hashing, JWT creation/validation.

Design decisions:
- bcrypt with cost factor 12 (good balance of security vs speed)
- Separate access/refresh token types to prevent token confusion attacks
- Token type claim prevents refresh tokens from being used as access tokens
- Short access token lifetime (15min) limits breach window
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings
from app.core.exceptions import InvalidTokenError

_BCRYPT_ROUNDS = 12


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password. Always use this, never store plain."""
    return bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash. Constant-time comparison."""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def _create_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Internal: create a signed JWT.
    Always includes: sub, type, iat, exp.
    """
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.APP_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: UUID, role: str = "user") -> str:
    """Create short-lived access token (15 min default)."""
    return _create_token(
        subject=str(user_id),
        token_type="access",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra_claims={"role": role},
    )


def create_refresh_token(user_id: UUID) -> str:
    """Create long-lived refresh token (7 days default)."""
    return _create_token(
        subject=str(user_id),
        token_type="refresh",
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate an access token.
    Raises InvalidTokenError on any failure — never leaks internal details.
    """
    try:
        payload = jwt.decode(
            token, settings.APP_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "access":
            raise InvalidTokenError("Wrong token type")
        return payload
    except JWTError:
        raise InvalidTokenError()


def decode_refresh_token(token: str) -> dict[str, Any]:
    """Decode and validate a refresh token."""
    try:
        payload = jwt.decode(
            token, settings.APP_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "refresh":
            raise InvalidTokenError("Wrong token type")
        return payload
    except JWTError:
        raise InvalidTokenError()
