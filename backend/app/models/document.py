"""Document and DocumentChunk models for RAG (Retrieval Augmented Generation).

Why two tables:
- Document: tracks the uploaded file + indexing status
- DocumentChunk: stores the parsed text segments with embeddings

The embedding column on DocumentChunk is a pgvector vector(1536) added via
migration (see backend/migrations/add_document_tables.sql). It is NOT declared
in the ORM model to avoid a hard pgvector-sqlalchemy dependency; all vector
operations use raw SQL via SQLAlchemy text().
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

# Valid document processing statuses
DOCUMENT_STATUS_PENDING = "pending"
DOCUMENT_STATUS_INDEXING = "indexing"
DOCUMENT_STATUS_READY = "ready"
DOCUMENT_STATUS_ERROR = "error"


class Document(Base, UUIDMixin, TimestampMixin):
    """
    Represents an uploaded file attached to a conversation.
    After upload, a background task parses + embeds the content and
    sets status → 'ready'. The frontend polls until ready.
    """

    __tablename__ = "documents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    # Relative path under settings.LOCAL_STORAGE_PATH
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    # pending | indexing | ready | error
    status: Mapped[str] = mapped_column(Text, default=DOCUMENT_STATUS_PENDING, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} filename={self.filename!r} status={self.status}>"


class DocumentChunk(Base, UUIDMixin):
    """
    A single text segment of a Document with its embedding vector.

    The `embedding` column (vector(1536)) is added via migration — see
    backend/migrations/add_document_tables.sql. All vector reads/writes
    use raw SQL to avoid pgvector ORM dependency.
    """

    __tablename__ = "document_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # metadata: page number, section title, etc.
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=__import__("sqlalchemy").text("now()"),
        nullable=False,
    )

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<DocumentChunk id={self.id} doc={self.document_id} idx={self.chunk_index}>"
