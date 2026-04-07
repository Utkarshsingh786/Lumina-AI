"""Auth service — user registration, login, token management."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthenticationError,
    EmailAlreadyExistsError,
    ConflictError,
    NotFoundError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.auth import RegisterRequest, TokenResponse
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)

# Pre-hashed dummy used for constant-time login response when the user doesn't exist.
# Computed once at import time so it's always a structurally valid bcrypt hash.
# This prevents user enumeration via timing differences.
_DUMMY_HASH: str = hash_password("__lumina_timing_protection_dummy__")


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)

    async def register(self, data: RegisterRequest) -> tuple[User, TokenResponse]:
        """
        Create a new user account.
        Returns user + tokens so frontend can log in immediately after signup.
        """
        email = data.email.lower()

        if await self.user_repo.email_exists(email):
            raise EmailAlreadyExistsError()

        if await self.user_repo.username_exists(data.username):
            raise ConflictError("Username already taken", error_code="USERNAME_EXISTS")

        user = await self.user_repo.create(
            email=email,
            username=data.username,
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
        )

        logger.info("auth.register", user_id=str(user.id), email=email)
        tokens = self._issue_tokens(user)
        return user, tokens

    async def login(self, email: str, password: str) -> tuple[User, TokenResponse]:
        """
        Authenticate user with email + password.
        Returns tokens on success, raises AuthenticationError on failure.
        We never distinguish between "wrong email" and "wrong password"
        to prevent user enumeration attacks.
        """
        email = email.lower()
        user = await self.user_repo.get_by_email(email)

        # Verify even if user doesn't exist (prevents timing attacks via user enumeration)
        stored_hash = user.hashed_password if user else _DUMMY_HASH

        if not verify_password(password, stored_hash) or not user:
            logger.warning("auth.login_failed", email=email)
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            raise AuthenticationError("Account is disabled")

        logger.info("auth.login", user_id=str(user.id))
        return user, self._issue_tokens(user)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        """Issue new access token using a valid refresh token."""
        payload = decode_refresh_token(refresh_token)
        user_id = UUID(payload["sub"])

        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        return self._issue_tokens(user)

    def _issue_tokens(self, user: User) -> TokenResponse:
        return TokenResponse(
            access_token=create_access_token(user.id, role=user.role),
            refresh_token=create_refresh_token(user.id),
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
