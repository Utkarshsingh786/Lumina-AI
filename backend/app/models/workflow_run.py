"""WorkflowRun model — persists agent workflow execution history."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDMixin


class WorkflowRun(Base, UUIDMixin):
    """
    Persists each agent workflow execution.
    Allows users to view history, inspect outputs, and re-run workflows.

    Columns:
      id            — UUID PK (gen_random_uuid)
      user_id       — FK to users
      workflow_id   — built-in workflow ID (e.g. "brainstorm")
      workflow_name — display name at run time (snapshot, in case definitions change)
      workflow_icon — emoji icon snapshot
      input         — user-provided input text
      model         — model string used for this run
      status        — running | completed | failed | cancelled
      step_results  — JSONB array: [{step, name, content, tokens}]
      total_tokens  — sum of tokens across all steps
      error         — error message if status == "failed"
      created_at    — when the run started
      completed_at  — when the run finished (null if still running)
    """

    __tablename__ = "workflow_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workflow_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    workflow_name: Mapped[str] = mapped_column(String(200), nullable=False)
    workflow_icon: Mapped[str] = mapped_column(String(10), nullable=False, server_default="⚡")
    input: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="running", index=True)
    step_results: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<WorkflowRun id={self.id} workflow={self.workflow_id} status={self.status}>"
