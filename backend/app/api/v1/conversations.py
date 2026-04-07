"""Conversations router — CRUD for conversations and messages."""

from uuid import UUID

import json as _json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_api_rate_limit
from app.core.exceptions import ConversationNotFoundError, PermissionDeniedError
from app.db.session import get_db
from app.models.user import User
from app.repositories.conversation_repo import ConversationRepository, MessageRepository
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetailResponse,
    ConversationListItem,
    ConversationResponse,
    ConversationUpdate,
    EditMessageRequest,
    MessageFeedbackRequest,
    MessageResponse,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


# ── Conversation CRUD ─────────────────────────────────

@router.get("", response_model=PaginatedResponse[ConversationListItem])
async def list_conversations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    include_archived: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ConversationListItem]:
    repo = ConversationRepository(db)
    offset = (page - 1) * page_size
    conversations = await repo.get_user_conversations(
        current_user.id, offset=offset, limit=page_size, include_archived=include_archived
    )
    total = await repo.count_user_conversations(current_user.id, include_archived)
    items = [ConversationListItem.model_validate(c) for c in conversations]
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=offset + page_size < total,
        has_prev=page > 1,
    )


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(require_api_rate_limit),
) -> ConversationResponse:
    repo = ConversationRepository(db)
    conv = await repo.create(
        user_id=current_user.id,
        title=data.title,
        model=data.model,
        persona=data.persona,
        system_prompt=data.system_prompt,
    )
    return ConversationResponse.model_validate(conv)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetailResponse:
    repo = ConversationRepository(db)
    conv = await repo.get_with_messages(conversation_id, current_user.id)
    if not conv:
        raise ConversationNotFoundError()
    return ConversationDetailResponse(
        **ConversationResponse.model_validate(conv).model_dump(),
        messages=[MessageResponse.model_validate(m) for m in conv.messages if not m.is_deleted],
    )


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: UUID,
    data: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    repo = ConversationRepository(db)
    conv = await repo.get_by_id(conversation_id)
    if not conv:
        raise ConversationNotFoundError()
    if conv.user_id != current_user.id:
        raise PermissionDeniedError()
    update_data = data.model_dump(exclude_none=True)
    updated = await repo.update(conv, **update_data)
    return ConversationResponse.model_validate(updated)


@router.delete("/{conversation_id}", response_model=SuccessResponse)
async def delete_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    repo = ConversationRepository(db)
    conv = await repo.get_by_id(conversation_id)
    if not conv:
        raise ConversationNotFoundError()
    if conv.user_id != current_user.id:
        raise PermissionDeniedError()
    await repo.delete(conv)
    return SuccessResponse(message="Conversation deleted")


@router.get("/{conversation_id}/export")
async def export_conversation(
    conversation_id: UUID,
    format: str = Query(default="markdown", pattern="^(json|markdown|txt)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Export a conversation in json, markdown, or txt format.
    Returns a file download (Content-Disposition: attachment).
    """
    repo = ConversationRepository(db)
    conv = await repo.get_with_messages(conversation_id, current_user.id)
    if not conv:
        raise ConversationNotFoundError()

    messages = [m for m in conv.messages if not m.is_deleted]
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in conv.title)[:60].strip()
    exported_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename_base = f"{safe_title or 'conversation'}_{exported_at}"

    if format == "json":
        payload = {
            "id": str(conv.id),
            "title": conv.title,
            "model": conv.model,
            "persona": conv.persona,
            "created_at": conv.created_at.isoformat(),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
                if m.role in ("user", "assistant")
            ],
        }
        body = _json.dumps(payload, indent=2, ensure_ascii=False)
        media_type = "application/json"
        filename = f"{filename_base}.json"

    elif format == "markdown":
        lines = [
            f"# {conv.title}",
            f"",
            f"**Model:** {conv.model}  ",
            f"**Persona:** {conv.persona}  ",
            f"**Exported:** {exported_at}",
            f"",
            "---",
            "",
        ]
        for m in messages:
            if m.role == "user":
                lines += [f"**You**", "", m.content, ""]
            elif m.role == "assistant":
                lines += [f"**Lumina**", "", m.content, ""]
        body = "\n".join(lines)
        media_type = "text/markdown"
        filename = f"{filename_base}.md"

    else:  # txt
        lines = [
            f"Conversation: {conv.title}",
            f"Model: {conv.model} | Persona: {conv.persona}",
            f"Exported: {exported_at}",
            "=" * 60,
            "",
        ]
        for m in messages:
            if m.role == "user":
                lines += ["[You]", m.content, ""]
            elif m.role == "assistant":
                lines += ["[Lumina]", m.content, ""]
        body = "\n".join(lines)
        media_type = "text/plain"
        filename = f"{filename_base}.txt"

    return Response(
        content=body.encode("utf-8"),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{conversation_id}/search")
async def search_in_conversation(
    conversation_id: UUID,
    q: str = Query(min_length=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageResponse]:
    """Full-text search within a conversation's messages."""
    from sqlalchemy import select
    from app.models.message import Message

    conv_repo = ConversationRepository(db)
    conv = await conv_repo.get_by_id(conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise ConversationNotFoundError()

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .where(Message.content.ilike(f"%{q}%"))
        .where(Message.is_deleted.is_(False))
        .limit(20)
    )
    messages = result.scalars().all()
    return [MessageResponse.model_validate(m) for m in messages]


# ── Message operations ────────────────────────────────

@router.delete("/messages/{message_id}", response_model=SuccessResponse)
async def delete_message(
    message_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    repo = MessageRepository(db)
    msg = await repo.get_by_id(message_id)
    if not msg:
        from app.core.exceptions import MessageNotFoundError
        raise MessageNotFoundError()
    if msg.user_id != current_user.id:
        raise PermissionDeniedError()
    await repo.update(msg, is_deleted=True)
    return SuccessResponse(message="Message deleted")


@router.patch("/messages/{message_id}", response_model=MessageResponse)
async def edit_message(
    message_id: UUID,
    data: EditMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    repo = MessageRepository(db)
    msg = await repo.get_by_id(message_id)
    if not msg:
        from app.core.exceptions import MessageNotFoundError
        raise MessageNotFoundError()
    if msg.user_id != current_user.id:
        raise PermissionDeniedError()
    updated = await repo.update(msg, content=data.content, is_edited=True)
    return MessageResponse.model_validate(updated)


@router.post("/messages/{message_id}/feedback", response_model=SuccessResponse)
async def submit_feedback(
    message_id: UUID,
    data: MessageFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    repo = MessageRepository(db)
    msg = await repo.get_by_id(message_id)
    if not msg:
        from app.core.exceptions import MessageNotFoundError
        raise MessageNotFoundError()
    await repo.upsert_feedback(message_id, current_user.id, data.rating, data.comment)
    return SuccessResponse(message="Feedback recorded")
