"""Conversation and message Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── Conversation ──────────────────────────────────────
class ConversationCreate(BaseModel):
    title: str = Field(default="New Chat", max_length=500)
    model: str = Field(default="gpt-4o", max_length=100)
    persona: str = Field(default="general", max_length=100)
    system_prompt: str | None = None


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=100)
    persona: str | None = Field(default=None, max_length=100)
    is_pinned: bool | None = None
    is_archived: bool | None = None
    system_prompt: str | None = None


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str
    model: str
    persona: str
    is_pinned: bool
    is_archived: bool
    is_public: bool
    share_token: str | None
    token_count: int
    message_count: int
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationListItem(BaseModel):
    """Lightweight version for sidebar listing — no messages."""
    id: uuid.UUID
    title: str
    model: str
    persona: str
    is_pinned: bool
    is_archived: bool
    is_public: bool
    share_token: str | None
    message_count: int
    last_message_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Messages ──────────────────────────────────────────
class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    content_type: str
    token_count: int | None
    is_edited: bool
    metadata: dict = Field(validation_alias="extra_metadata")
    created_at: datetime

    model_config = {"from_attributes": True}


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=32_000)
    model: str | None = None          # override conversation model for this message
    stream: bool = True


class MessageFeedbackRequest(BaseModel):
    rating: Literal[-1, 1]
    comment: str | None = Field(default=None, max_length=2000)


class EditMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=32_000)


# ── Chat Request (triggers AI response) ───────────────
class ChatRequest(BaseModel):
    """
    Full chat request body. Sent to POST /conversations/{id}/chat.
    The model is fixed to conversation.model — set it when creating the conversation,
    not on individual messages. This guarantees every message in a conversation
    uses the same model.
    """
    content: str = Field(min_length=1, max_length=32_000)
    stream: bool = Field(default=True)
    # Tool use options
    enable_tools: bool = Field(default=False)
    tool_names: list[str] | None = None


class ChatNonStreamResponse(BaseModel):
    """Response when stream=False."""
    message: MessageResponse
    usage: dict


class StreamInitResponse(BaseModel):
    """Returned when stream=True — client uses stream_id to open SSE."""
    stream_id: str
    conversation_id: uuid.UUID
    user_message_id: uuid.UUID


# ── Conversation with Messages ────────────────────────
class ConversationDetailResponse(ConversationResponse):
    messages: list[MessageResponse] = []
