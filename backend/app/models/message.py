"""Message and AI generation models."""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class Message(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # role: user | assistant | system | tool
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), default="text", nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    # parent_id enables message branching / edit history
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL")
    )
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Stores: citations, tool_call_ids, rag_sources, suggested_followups, etc.
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
    ai_generation: Mapped["AIGeneration | None"] = relationship(
        "AIGeneration", back_populates="message", uselist=False, cascade="all, delete-orphan"
    )
    feedback: Mapped["MessageFeedback | None"] = relationship(
        "MessageFeedback", back_populates="message", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Message id={self.id} role={self.role} conv={self.conversation_id}>"


class AIGeneration(Base, UUIDMixin):
    """
    Tracks every LLM API call separately from the message.
    Critical for cost tracking, debugging, and usage analytics.
    Decoupled from Message so we can log failed generations too.
    """

    __tablename__ = "ai_generations"

    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    finish_reason: Mapped[str | None] = mapped_column(String(50))
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 8))
    error: Mapped[str | None] = mapped_column(Text)

    from app.db.base import TimestampMixin
    from sqlalchemy import DateTime, text
    from sqlalchemy.orm import mapped_column as mc

    # created_at only (no updated_at needed for immutable generation records)
    from datetime import datetime
    from sqlalchemy import DateTime, text as sa_text
    created_at: Mapped[datetime] = mapped_column(
        "created_at",
        __import__("sqlalchemy").DateTime(timezone=True),
        server_default=__import__("sqlalchemy").text("now()"),
        nullable=False,
    )

    message: Mapped["Message | None"] = relationship("Message", back_populates="ai_generation")


class MessageFeedback(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "message_feedback"

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # 1 = thumbs up, -1 = thumbs down
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    message: Mapped["Message"] = relationship("Message", back_populates="feedback")
