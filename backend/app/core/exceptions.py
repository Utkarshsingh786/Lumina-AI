"""
Custom exception hierarchy for Lumina.

Why a custom hierarchy:
- Consistent error responses across the entire API
- HTTP status codes live in one place, not scattered across handlers
- Easy to catch specific error categories at middleware level
- Structured error bodies for frontend consumption
"""

from typing import Any


class LuminaError(Exception):
    """Base exception. All app errors inherit from this."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: str | None = None,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.error_code = error_code or self.__class__.error_code
        self.details = details or {}
        super().__init__(self.message)


# ── 400 Bad Request ───────────────────────────────────
class ValidationError(LuminaError):
    status_code = 400
    error_code = "VALIDATION_ERROR"
    message = "Invalid request data"


class BadRequestError(LuminaError):
    status_code = 400
    error_code = "BAD_REQUEST"
    message = "Bad request"


# ── 401 Unauthorized ──────────────────────────────────
class AuthenticationError(LuminaError):
    status_code = 401
    error_code = "AUTHENTICATION_FAILED"
    message = "Authentication required"


class InvalidTokenError(LuminaError):
    status_code = 401
    error_code = "INVALID_TOKEN"
    message = "Invalid or expired token"


# ── 403 Forbidden ─────────────────────────────────────
class PermissionDeniedError(LuminaError):
    status_code = 403
    error_code = "PERMISSION_DENIED"
    message = "You do not have permission to perform this action"


# ── 404 Not Found ─────────────────────────────────────
class NotFoundError(LuminaError):
    status_code = 404
    error_code = "NOT_FOUND"
    message = "Resource not found"


class ConversationNotFoundError(NotFoundError):
    error_code = "CONVERSATION_NOT_FOUND"
    message = "Conversation not found"


class MessageNotFoundError(NotFoundError):
    error_code = "MESSAGE_NOT_FOUND"
    message = "Message not found"


# ── 409 Conflict ──────────────────────────────────────
class ConflictError(LuminaError):
    status_code = 409
    error_code = "CONFLICT"
    message = "Resource already exists"


class EmailAlreadyExistsError(ConflictError):
    error_code = "EMAIL_EXISTS"
    message = "An account with this email already exists"


# ── 429 Rate Limit ────────────────────────────────────
class RateLimitError(LuminaError):
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    message = "Too many requests. Please slow down."


# ── 500 Server Errors ─────────────────────────────────
class AIProviderError(LuminaError):
    status_code = 502
    error_code = "AI_PROVIDER_ERROR"
    message = "AI provider returned an error"


class AITimeoutError(LuminaError):
    status_code = 504
    error_code = "AI_TIMEOUT"
    message = "AI provider timed out"


class StorageError(LuminaError):
    status_code = 500
    error_code = "STORAGE_ERROR"
    message = "File storage operation failed"
