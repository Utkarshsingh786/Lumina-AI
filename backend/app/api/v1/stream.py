"""
Streaming chat endpoint using Server-Sent Events (SSE).

SSE protocol:
- Client makes GET request, keeps connection open
- Server pushes data: events as they arrive
- Format: "data: {json}\\n\\n"
- Special events: "event: done\\n" to signal completion

Why SSE and not WebSockets here:
- Unidirectional stream (server → client) is exactly what SSE is for
- Works through HTTP/2, CDNs, and proxies without configuration
- Browser EventSource API handles reconnection automatically
- Simpler auth (just Authorization header on initial request)
- WebSockets are better for collaborative features (Phase 3)

Flow:
1. Client POSTs to /conversations/{id}/chat with message
2. Server saves user message, starts AI streaming
3. Tokens are sent as SSE events
4. Client receives and renders them progressively
"""

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_chat_rate_limit
from app.core.exceptions import ConversationNotFoundError, PermissionDeniedError
from app.db.session import get_db
from app.models.user import User
from app.repositories.conversation_repo import ConversationRepository
from app.schemas.conversation import ChatRequest, ChatNonStreamResponse
from app.services.chat_service import ChatService
from app.core.logging import get_logger

router = APIRouter(tags=["chat"])
logger = get_logger(__name__)


def _sse_event(data: dict, event: str | None = None) -> str:
    """Format a dict as an SSE event string."""
    lines = []
    if event:
        lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data)}")
    lines.append("")  # blank line terminates event
    lines.append("")
    return "\n".join(lines)


def _sse_comment(text: str) -> str:
    """SSE comment — used as keepalive ping."""
    return f": {text}\n\n"


@router.post("/conversations/{conversation_id}/chat")
async def chat(
    conversation_id: UUID,
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(require_chat_rate_limit),
) -> StreamingResponse:
    """
    Main chat endpoint.

    If stream=True: returns an SSE stream (Content-Type: text/event-stream)
    If stream=False: returns a JSON response with the full message

    The frontend should always prefer stream=True for better UX.
    stream=False is useful for API clients and tool-calling pipelines.
    """
    conv_repo = ConversationRepository(db)
    conv = await conv_repo.get_by_id(conversation_id)

    if not conv:
        raise ConversationNotFoundError()
    if conv.user_id != current_user.id:
        raise PermissionDeniedError()

    chat_service = ChatService(db)

    if not request.stream:
        # Non-streaming path
        msg, completion = await chat_service.chat_complete(
            conversation=conv,
            user_message=request.content,
            user_id=current_user.id,
        )
        from app.schemas.conversation import MessageResponse
        return ChatNonStreamResponse(
            message=MessageResponse.model_validate(msg),
            usage={
                "prompt_tokens": completion.prompt_tokens,
                "completion_tokens": completion.completion_tokens,
                "total_tokens": completion.total_tokens,
                "latency_ms": completion.latency_ms,
            },
        )

    # Streaming path
    async def event_generator():
        # Initial ping to establish connection
        yield _sse_comment("connected")

        try:
            async for chunk in chat_service.chat_stream(
                conversation=conv,
                user_message=request.content,
                user_id=current_user.id,
                attached_document_ids=request.attached_document_ids or None,
            ):
                if chunk["type"] == "token":
                    yield _sse_event({"type": "token", "content": chunk["content"]})
                elif chunk["type"] == "tool_use":
                    yield _sse_event(
                        {
                            "type": "tool_use",
                            "tool_name": chunk["tool_name"],
                            "input": chunk.get("input", {}),
                        },
                        event="tool_use",
                    )
                elif chunk["type"] == "tool_result":
                    yield _sse_event(
                        {
                            "type": "tool_result",
                            "tool_name": chunk["tool_name"],
                            "result": chunk["result"],
                            "is_error": chunk.get("is_error", False),
                        },
                        event="tool_result",
                    )
                elif chunk["type"] == "done":
                    yield _sse_event(
                        {
                            "type": "done",
                            "message_id": chunk["message_id"],
                            "usage": chunk["usage"],
                        },
                        event="done",
                    )
                elif chunk["type"] == "error":
                    yield _sse_event(
                        {"type": "error", "message": chunk["message"]},
                        event="error",
                    )

        except asyncio.CancelledError:
            # Client disconnected mid-stream — this is normal, not an error
            logger.info(
                "stream.client_disconnected",
                conversation_id=str(conversation_id),
                user_id=str(current_user.id),
            )

        finally:
            yield _sse_event({"type": "close"}, event="close")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # Disable nginx buffering
            "Connection": "keep-alive",
        },
    )


@router.post("/conversations/{conversation_id}/regenerate")
async def regenerate_last_response(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(require_chat_rate_limit),
) -> StreamingResponse:
    """
    Regenerate the last assistant response.
    Deletes the previous assistant message and re-runs the last user message.
    """
    from app.models.message import Message
    from sqlalchemy import select, desc

    conv_repo = ConversationRepository(db)
    conv = await conv_repo.get_by_id(conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise ConversationNotFoundError()

    # Find and soft-delete last assistant message
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .where(Message.role == "assistant")
        .where(Message.is_deleted.is_(False))
        .order_by(desc(Message.created_at))
        .limit(1)
    )
    last_assistant = result.scalar_one_or_none()
    if last_assistant:
        last_assistant.is_deleted = True
        await db.flush()

    # Find the last user message to re-use
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .where(Message.role == "user")
        .where(Message.is_deleted.is_(False))
        .order_by(desc(Message.created_at))
        .limit(1)
    )
    last_user_msg = result.scalar_one_or_none()
    if not last_user_msg:
        raise ConversationNotFoundError("No user message to regenerate from")

    chat_service = ChatService(db)

    async def event_generator():
        yield _sse_comment("connected")
        async for chunk in chat_service.chat_stream(
            conversation=conv,
            user_message=last_user_msg.content,
            user_id=current_user.id,
            existing_user_msg=last_user_msg,
        ):
            if chunk["type"] == "token":
                yield _sse_event({"type": "token", "content": chunk["content"]})
            elif chunk["type"] == "done":
                yield _sse_event(chunk, event="done")
            elif chunk["type"] == "error":
                yield _sse_event(chunk, event="error")
        yield _sse_event({"type": "close"}, event="close")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
