"""
SQLAlchemy declarative base with shared column mixins.

Using DeclarativeBase from SQLAlchemy 2.0 (not the old declarative_base() function).
Mixins provide consistent timestamps and primary keys without repetition.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    All ORM models inherit from this.
    Provides type-safe mapped_column declarations via SQLAlchemy 2.0 typing.
    """
    pass


class TimestampMixin:
    """
    Adds created_at / updated_at to any model.
    server_default uses PostgreSQL's now() for accuracy even if app clock drifts.
    onupdate ensures updated_at is always fresh.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class UUIDMixin:
    """UUID primary key using PostgreSQL's gen_random_uuid()."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        nullable=False,
    )
