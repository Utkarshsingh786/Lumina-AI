"""
Share conversation links.

Endpoints:
  POST   /conversations/{id}/share    — generate a public share token
  DELETE /conversations/{id}/share    — revoke the share token
  GET    /share/{token}               — public endpoint (no auth) to view a shared conversation

Design notes:
- share_token is a 32-byte URL-safe random string (urlsafe_b64encode) — not guessable
- The public endpoint returns full message history (role == user/assistant only)
- Revoking sets is_public=False and clears share_token atomically
"""

import secrets
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import ConversationNotFoundError, NotFoundError, PermissionDeniedError
from app.db.session import get_db
from app.models.user import User
from app.repositories.conversation_repo import ConversationRepository
from app.schemas.conversation import ConversationDetailResponse, ConversationResponse, MessageResponse
from app.schemas.common import SuccessResponse

router = APIRouter(tags=["share"])


@router.post(
    "/conversations/{conversation_id}/share",
    response_model=ConversationResponse,
    summary="Generate a public share link for a conversation",
)
async def share_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """
    Generates a cryptographically-random share token and marks the conversation
    as public. Anyone with the token URL can read the conversation without auth.
    Calling this endpoint again on an already-shared conversation re-uses the
    existing token (idempotent).
    """
    repo = ConversationRepository(db)
    conv = await repo.get_by_id(conversation_id)
    if not conv:
        raise ConversationNotFoundError()
    if conv.user_id != current_user.id:
        raise PermissionDeniedError()

    if not conv.share_token:
        # Generate a 32-byte URL-safe token — 43 characters, extremely hard to guess
        conv.share_token = secrets.token_urlsafe(32)

    conv.is_public = True
    await db.commit()
    await db.refresh(conv)
    return ConversationResponse.model_validate(conv)


@router.delete(
    "/conversations/{conversation_id}/share",
    response_model=SuccessResponse,
    summary="Revoke the share link for a conversation",
)
async def unshare_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    """
    Clears the share token and marks the conversation private. Any existing
    share URLs immediately stop working (403 from the public endpoint).
    """
    repo = ConversationRepository(db)
    conv = await repo.get_by_id(conversation_id)
    if not conv:
        raise ConversationNotFoundError()
    if conv.user_id != current_user.id:
        raise PermissionDeniedError()

    conv.share_token = None
    conv.is_public = False
    await db.commit()
    return SuccessResponse(message="Share link revoked")


@router.get(
    "/share/{token}",
    response_model=ConversationDetailResponse,
    summary="View a publicly shared conversation (no auth required)",
)
async def get_shared_conversation(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> ConversationDetailResponse:
    """
    Public endpoint — no JWT required. Returns the full conversation
    (user + assistant messages only) for a valid, active share token.
    Returns 404 if token doesn't exist or the conversation was unshared.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.conversation import Conversation

    result = await db.execute(
        select(Conversation)
        .where(Conversation.share_token == token)
        .where(Conversation.is_public.is_(True))
        .options(selectinload(Conversation.messages))
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise NotFoundError("Shared conversation not found or link has been revoked")

    visible_messages = [
        MessageResponse.model_validate(m)
        for m in conv.messages
        if not m.is_deleted and m.role in ("user", "assistant")
    ]

    return ConversationDetailResponse(
        **ConversationResponse.model_validate(conv).model_dump(),
        messages=visible_messages,
    )
