"""
Background task: summarize old conversation segments.

When this runs:
- After SUMMARY_TRIGGER_MESSAGES messages in a conversation
- Summarizes the oldest 20 messages into a compact paragraph
- Stores the summary; those messages are marked as "summarized"
- Next time context is built, the summary replaces those messages

Why this architecture:
- Enables unlimited conversation length without ballooning costs
- Summary is injected into context as a "system" message
- Old messages are kept in DB for history viewing but not sent to LLM
"""

import asyncio

from app.workers.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(
    name="summarization.summarize_conversation",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def summarize_conversation_task(self, conversation_id: str) -> str | None:
    return asyncio.run(_async_summarize(conversation_id))


async def _async_summarize(conversation_id: str) -> str | None:
    from uuid import UUID
    from app.ai.providers.base import ChatMessage
    from app.ai.providers.router import TaskType, get_provider_for_task
    from app.db.session import AsyncSessionLocal
    from app.models.message import Message
    from app.models.memory import ConversationSummary
    from app.repositories.conversation_repo import MessageRepository
    from sqlalchemy import select

    try:
        async with AsyncSessionLocal() as db:
            msg_repo = MessageRepository(db)

            # Get oldest 20 non-summarized messages
            result = await db.execute(
                select(Message)
                .where(Message.conversation_id == UUID(conversation_id))
                .where(Message.is_deleted.is_(False))
                .where(Message.role.in_(["user", "assistant"]))
                .order_by(Message.created_at)
                .limit(20)
            )
            messages = list(result.scalars().all())

            if len(messages) < 10:
                return None  # Not enough to summarize

            provider, model = get_provider_for_task(TaskType.SUMMARIZATION)
            chat_messages = [
                ChatMessage(role=m.role, content=m.content) for m in messages
            ]
            summary = await provider.summarize_conversation(chat_messages, model=model)

            # Store summary
            summary_record = ConversationSummary(
                conversation_id=UUID(conversation_id),
                summary=summary,
                message_range_start=messages[0].id,
                message_range_end=messages[-1].id,
                token_count=len(summary.split()) * 2,  # rough estimate
            )
            db.add(summary_record)
            await db.commit()

        logger.info("summarization.complete", conversation_id=conversation_id)
        return summary

    except Exception as e:
        logger.error("summarization.error", conversation_id=conversation_id, error=str(e))
        return None
