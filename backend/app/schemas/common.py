"""Shared Pydantic schema utilities."""

from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated list response."""
    items: list[T]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool


class ErrorResponse(BaseModel):
    """Standard error response shape for all API errors."""
    error_code: str
    message: str
    details: dict = {}


class SuccessResponse(BaseModel):
    """Simple success acknowledgement."""
    success: bool = True
    message: str = "OK"
