"""
Context window builder — the most important AI infrastructure component.

Responsibility: given a conversation and current request, assemble the
optimal list of messages to send to the LLM.

The assembly order (and priority for trimming):
  1. System prompt (never trimmed)
  2. Conversation summary (if messages were compressed)
  3. Long-term memory facts (trimmed last)
  4. RAG context (trimmed second)
  5. Recent messages (trimmed oldest first)
  6. Current user message (never trimmed)

Why this matters:
- Naive approach: stuff all messages → hit token limit → error or truncation
- Production approach: smart sliding window + summarization = unlimited conversation length
- This is how real AI products work (ChatGPT, Claude.ai, etc.)
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts.system import build_system_prompt
from app.ai.providers.base import ChatMessage
from app.core.config import settings
from app.core.logging import get_logger
from app.models.message import Message
from app.utils.tokens import count_message_tokens, count_messages_tokens, count_tokens

logger = get_logger(__name__)


class ContextBuilder:
    """
    Builds the optimal context window for an AI request.

    Usage:
        builder = ContextBuilder(db, conversation, user_id)
        messages = await builder.build(current_user_message)
    """

    def __init__(
        self,
        history: list[Message],
        persona: str = "general",
        model: str = "gpt-4o",
        custom_system_prompt: str | None = None,
        memories: list[str] | None = None,
        rag_context: str | None = None,
        conversation_summary: str | None = None,
        enable_tools: bool = False,
        max_context_tokens: int | None = None,
    ) -> None:
        self.history = history
        self.persona = persona
        self.model = model
        self.custom_system_prompt = custom_system_prompt
        self.memories = memories or []
        self.rag_context = rag_context
        self.conversation_summary = conversation_summary
        self.enable_tools = enable_tools
        self.max_tokens = max_context_tokens or settings.MAX_CONTEXT_TOKENS
        self.reserve_tokens = settings.CONTEXT_RESERVE_TOKENS

    def _get_token_budget(self) -> int:
        """Available tokens for context (total - reserve for response)."""
        return self.max_tokens - self.reserve_tokens

    def build(self, current_user_message: str) -> list[ChatMessage]:
        """
        Assemble the context window.
        Returns list of ChatMessage objects ready to send to provider.
        """
        budget = self._get_token_budget()

        # 1. Build system prompt (always included)
        system_text = build_system_prompt(
            persona=self.persona,
            memories=self.memories if self.memories else None,
            rag_context=self.rag_context,
            custom_system_prompt=self.custom_system_prompt,
            enable_tools=self.enable_tools,
        )
        system_tokens = count_tokens(system_text, self.model)
        remaining = budget - system_tokens

        # 2. Allocate space for current user message (must always fit)
        current_msg_tokens = count_message_tokens("user", current_user_message, self.model)
        remaining -= current_msg_tokens

        if remaining <= 0:
            # Extreme edge case: system prompt + message alone exceed budget
            logger.warning(
                "context.budget_exceeded",
                system_tokens=system_tokens,
                current_msg_tokens=current_msg_tokens,
                budget=budget,
            )

        # 3. Fit as many history messages as possible (newest first)
        selected_history: list[Message] = []
        for msg in reversed(self.history):
            msg_tokens = count_message_tokens(msg.role, msg.content, self.model)
            if remaining - msg_tokens >= 0:
                selected_history.insert(0, msg)
                remaining -= msg_tokens
            else:
                # Can't fit this message — stop (we've gone past the budget)
                logger.debug(
                    "context.message_trimmed",
                    trimmed_message_id=str(msg.id),
                    remaining_budget=remaining,
                )
                break

        # 4. Inject conversation summary if messages were trimmed
        messages: list[ChatMessage] = [ChatMessage(role="system", content=system_text)]

        if len(selected_history) < len(self.history) and self.conversation_summary:
            # Some messages were trimmed — inject their summary for continuity
            messages.append(
                ChatMessage(
                    role="system",
                    content=f"[Earlier conversation summary]\n{self.conversation_summary}",
                )
            )

        # 5. Add selected history
        for msg in selected_history:
            messages.append(ChatMessage(role=msg.role, content=msg.content))

        # 6. Add current user message
        messages.append(ChatMessage(role="user", content=current_user_message))

        logger.debug(
            "context.built",
            total_messages=len(messages),
            history_included=len(selected_history),
            history_available=len(self.history),
            system_tokens=system_tokens,
        )

        return messages
