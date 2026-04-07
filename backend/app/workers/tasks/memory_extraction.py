"""
Background task: extract long-term memory facts from conversations.

Why this feature matters:
- Persistent memory is what makes AI assistants feel "smart" over time
- "You mentioned you work in Python last month" — that's the premium product experience
- Users feel heard and understood without re-explaining context each time

What we extract:
- Personal facts: name, job title, location, expertise
- Preferences: "I prefer concise answers", "always use TypeScript"
- Instructions: "always respond in Spanish"
- Project context: current tech stack, goals, constraints

What we DON'T extract:
- Transient questions (weather, jokes, one-off lookups)
- Content that might be private or sensitive beyond the conversation
"""

import asyncio
import json

from app.workers.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(
    name="memory_extraction.extract_memory",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def extract_memory_task(
    self,
    user_id: str,
    conversation_id: str,
    user_message: str,
    assistant_response: str,
) -> list[dict] | None:
    return asyncio.run(
        _async_extract_memory(user_id, conversation_id, user_message, assistant_response)
    )


async def _async_extract_memory(
    user_id: str,
    conversation_id: str,
    user_message: str,
    assistant_response: str,
) -> list[dict] | None:
    from app.ai.prompts.system import MEMORY_EXTRACTION_PROMPT
    from app.ai.providers.base import ChatMessage
    from app.ai.providers.router import TaskType, get_provider_for_task
    from app.db.session import AsyncSessionLocal
    from app.models.memory import MemoryEntry
    from uuid import UUID

    try:
        conversation_text = f"User: {user_message}\n\nAssistant: {assistant_response}"

        provider, model = get_provider_for_task(TaskType.FAST)
        response = await provider.chat_completion(
            messages=[
                ChatMessage(role="system", content=MEMORY_EXTRACTION_PROMPT),
                ChatMessage(role="user", content=conversation_text),
            ],
            model=model,
            max_tokens=500,
            temperature=0.1,
        )

        # Parse JSON response
        content = response.content.strip()
        if not content or content == "[]":
            return []

        memories = json.loads(content)
        if not isinstance(memories, list):
            return []

        # Save to DB
        async with AsyncSessionLocal() as db:
            for memory in memories[:5]:  # max 5 per exchange
                if not memory.get("content"):
                    continue
                entry = MemoryEntry(
                    user_id=UUID(user_id),
                    conversation_id=UUID(conversation_id),
                    content=memory["content"],
                    memory_type=memory.get("type", "fact"),
                    importance=max(1, min(10, memory.get("importance", 5))),
                )
                db.add(entry)
            await db.commit()

        logger.info(
            "memory_extraction.complete",
            user_id=user_id,
            extracted_count=len(memories),
        )
        return memories

    except json.JSONDecodeError:
        logger.warning("memory_extraction.json_parse_error", user_id=user_id)
        return []
    except Exception as e:
        logger.error("memory_extraction.error", user_id=user_id, error=str(e))
        return None
