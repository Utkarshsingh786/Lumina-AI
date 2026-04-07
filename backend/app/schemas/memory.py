"""Pydantic schemas for memory endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MemoryEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content: str
    memory_type: str
    importance: int
    is_active: bool
    conversation_id: uuid.UUID | None
    created_at: datetime
    expires_at: datetime | None
    metadata: dict = Field(validation_alias="extra_metadata")


class MemoryToggleRequest(BaseModel):
    is_active: bool
