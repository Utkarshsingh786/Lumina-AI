"""Long-term memory and conversation summary models."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class MemoryEntry(Base, UUIDMixin, TimestampMixin):
    """
    Stores extracted facts/preferences about a user across conversations.
    These get injected into future chat contexts to give the AI "memory".

    Why separate from messages:
    - Messages are conversation-scoped; memory is user-scoped and persistent
    - Enables cross-conversation continuity ("you mentioned you like Python...")
    - Can be curated, deleted, or updated by the user
    """

    __tablename__ = "memory_entries"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL")
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # fact | preference | instruction | context
    memory_type: Mapped[str] = mapped_column(Text, default="fact", nullable=False)
    importance: Mapped[int] = mapped_column(SmallInteger, default=5, nullable=False)
    # pgvector column — added via migration with: ALTER TABLE ... ADD COLUMN embedding vector(1536)
    # We store as Text here and cast in queries to avoid hard sqlalchemy-pgvector dependency
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="memory_entries")

    def __repr__(self) -> str:
        return f"<MemoryEntry id={self.id} type={self.memory_type} user={self.user_id}>"


class ConversationSummary(Base, UUIDMixin):
    """
    Compressed summaries of conversation segments.
    Used when conversation exceeds token limit — old messages are replaced
    by their summary to keep context window manageable.
    """

    __tablename__ = "conversation_summaries"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    message_range_start: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL")
    )
    message_range_end: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL")
    )
    token_count: Mapped[int | None] = mapped_column(Integer)

    from datetime import datetime
    created_at: Mapped[datetime] = mapped_column(
        __import__("sqlalchemy").DateTime(timezone=True),
        server_default=__import__("sqlalchemy").text("now()"),
        nullable=False,
    )
