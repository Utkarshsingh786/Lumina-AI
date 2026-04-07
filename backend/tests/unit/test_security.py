"""Unit tests for security utilities — no DB needed."""

import pytest
from uuid import uuid4
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)
from app.core.exceptions import InvalidTokenError


def test_password_hashing():
    plain = "TestPassword123!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed)
    assert not verify_password("WrongPassword", hashed)


def test_access_token_create_and_decode():
    user_id = uuid4()
    token = create_access_token(user_id, role="user")
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"
    assert payload["role"] == "user"


def test_refresh_token_type_separation():
    """Refresh tokens must not be accepted as access tokens."""
    user_id = uuid4()
    refresh = create_refresh_token(user_id)
    with pytest.raises(InvalidTokenError):
        decode_access_token(refresh)  # should fail — wrong type


def test_invalid_token_raises():
    with pytest.raises(InvalidTokenError):
        decode_access_token("not.a.valid.token")
