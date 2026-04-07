"""Pydantic schemas for document endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID | None
    filename: str
    file_type: str
    file_size: int
    status: str  # pending | indexing | ready | error
    chunk_count: int
    error_message: str | None
    created_at: datetime
