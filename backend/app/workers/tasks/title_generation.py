"""
Background task: generate conversation title from first message.

Why background:
- Title generation is a separate LLM call (~500ms)
- User doesn't need to wait for it — the chat response is already streaming
- If it fails, the conversation just keeps its default title ("New Chat")

When it runs: after the first user message in a conversation
"""

import asyncio
from uuid import UUID

from app.workers.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(
    name="title_generation.generate_title",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def generate_title_task(self, conversation_id: str, first_message: str) -> str | None:
    """
    Generate a conversation title using a fast/cheap model.
    Updates the conversation record in DB.
    """
    return asyncio.run(_async_generate_title(conversation_id, first_message))


async def _async_generate_title(conversation_id: str, first_message: str) -> str | None:
    from app.db.session import AsyncSessionLocal
    from app.repositories.conversation_repo import ConversationRepository
    from app.ai.providers.router import get_provider_for_task, TaskType

    try:
        provider, model = get_provider_for_task(TaskType.FAST)
        title = await provider.generate_title(first_message, model=model)

        async with AsyncSessionLocal() as db:
            repo = ConversationRepository(db)
            conv = await repo.get_by_id(UUID(conversation_id))
            if conv and conv.title == "New Chat":
                await repo.update(conv, title=title)
                await db.commit()

        logger.info("title_generation.complete", conversation_id=conversation_id, title=title)
        return title

    except Exception as e:
        logger.error("title_generation.error", conversation_id=conversation_id, error=str(e))
        return None
