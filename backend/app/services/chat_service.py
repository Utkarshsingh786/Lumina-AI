"""
ChatService — orchestrates the full AI chat pipeline.

This is the heart of the application. It:
1. Saves the user's message
2. Retrieves conversation history
3. Loads long-term memory for the user
4. Builds the context window
5. Calls the AI provider (streaming or non-streaming)
6. Saves the AI response
7. Records token usage and cost
8. Triggers background tasks (title gen, summarization, memory extraction)

Phase 2 addition: agentic tool-calling loop.
When TOOLS_ENABLED, the service runs up to TOOLS_MAX_ROUNDS of:
  chat_completion → detect tool_calls → execute tools → append results → repeat
Then emits the final text response as chunked tokens (simulated streaming).
The non-tool path is unchanged: full streaming via stream_completion().

Why separate service from router:
- Services contain business logic; routers handle HTTP concerns only
- Testable without HTTP stack
- Reusable from background workers (e.g., automated test conversations)
"""

import asyncio
import time
from collections.abc import AsyncGenerator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context.builder import ContextBuilder
from app.ai.providers.base import ChatMessage, CompletionResponse
from app.ai.providers.router import compute_cost, get_provider_for_model
from app.core.config import settings
from app.core.exceptions import ConversationNotFoundError, PermissionDeniedError
from app.core.logging import get_logger
from app.models.conversation import Conversation
from app.models.message import Message
from app.repositories.conversation_repo import ConversationRepository, MessageRepository

logger = get_logger(__name__)

# How long to sleep between emitted chunks when fake-streaming a tool response (seconds)
_CHUNK_SLEEP_S = 0.008
_CHUNK_SIZE = 5  # characters per token chunk


class ChatService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.conv_repo = ConversationRepository(db)
        self.msg_repo = MessageRepository(db)

    async def get_or_create_conversation(
        self,
        user_id: UUID,
        conversation_id: UUID | None = None,
        model: str | None = None,
        persona: str = "general",
    ) -> Conversation:
        """Get existing or create new conversation for user."""
        if conversation_id:
            conv = await self.conv_repo.get_by_id(conversation_id)
            if not conv:
                raise ConversationNotFoundError()
            if conv.user_id != user_id:
                raise PermissionDeniedError()
            return conv

        return await self.conv_repo.create(
            user_id=user_id,
            model=model or settings.DEFAULT_CHAT_MODEL,
            persona=persona,
        )

    async def save_user_message(
        self,
        conversation_id: UUID,
        user_id: UUID,
        content: str,
    ) -> Message:
        """Persist user message and update conversation metadata."""
        from app.utils.tokens import count_message_tokens

        token_count = count_message_tokens("user", content)
        msg = await self.msg_repo.create(
            conversation_id=conversation_id,
            user_id=user_id,
            role="user",
            content=content,
            token_count=token_count,
        )
        await self.conv_repo.touch_last_message(conversation_id)
        return msg

    async def save_assistant_message(
        self,
        conversation_id: UUID,
        user_id: UUID,
        content: str,
        metadata: dict | None = None,
    ) -> Message:
        """Persist the AI's response."""
        from app.utils.tokens import count_message_tokens

        token_count = count_message_tokens("assistant", content)
        msg = await self.msg_repo.create(
            conversation_id=conversation_id,
            user_id=user_id,
            role="assistant",
            content=content,
            token_count=token_count,
            extra_metadata=metadata or {},
        )
        await self.conv_repo.touch_last_message(conversation_id)
        return msg

    async def record_generation(
        self,
        message_id: UUID,
        conversation_id: UUID,
        completion: CompletionResponse,
    ) -> None:
        """Record AI generation metadata for billing/analytics.

        cost_usd: use provider-reported value when available; fall back to the
        central MODEL_PRICING table so the field is always populated.
        """
        cost = completion.cost_usd
        if cost is None:
            cost = compute_cost(completion.model, completion.prompt_tokens, completion.completion_tokens)

        await self.msg_repo.create_ai_generation(
            message_id=message_id,
            conversation_id=conversation_id,
            provider=completion.provider,
            model=completion.model,
            prompt_tokens=completion.prompt_tokens,
            completion_tokens=completion.completion_tokens,
            total_tokens=completion.total_tokens,
            latency_ms=completion.latency_ms,
            finish_reason=completion.finish_reason,
            cost_usd=cost,
        )
        # Update conversation token count
        if completion.total_tokens:
            await self.conv_repo.update_token_count(conversation_id, completion.total_tokens)

    async def _build_context(
        self,
        conversation: Conversation,
        current_message: str,
        user_memories: list[str] | None = None,
        enable_tools: bool = False,
    ) -> list:
        """Internal: retrieve history and build context window."""
        history = await self.msg_repo.get_recent_messages(
            conversation.id, limit=100  # We'll trim inside ContextBuilder
        )

        # TODO Phase 2: Load conversation summary if exists

        # RAG context injection — retrieve relevant document chunks if any exist
        rag_context: str | None = None
        try:
            from app.ai.rag.retriever import get_rag_context
            rag_context = await get_rag_context(
                db=self.db,
                user_id=conversation.user_id,
                conversation_id=conversation.id,
                query=current_message,
            )
        except Exception as e:
            logger.warning("chat_service.rag_error", error=str(e))

        builder = ContextBuilder(
            history=history,
            persona=conversation.persona,
            model=conversation.model,
            custom_system_prompt=conversation.system_prompt,
            memories=user_memories,
            rag_context=rag_context,
            enable_tools=enable_tools,
        )
        return builder.build(current_message)

    # ──────────────────────────────────────────────────────────────────────────
    # Agentic tool loop
    # ──────────────────────────────────────────────────────────────────────────

    async def _chat_with_tools(
        self,
        conversation: Conversation,
        user_message: str,
        user_id: UUID,
        model: str,
    ) -> AsyncGenerator[dict, None]:
        """
        Agentic loop that handles tool calling.

        Yields the same event types as chat_stream():
          {"type": "tool_use",    "tool_name": str, "input": dict}
          {"type": "tool_result", "tool_name": str, "result": str, "is_error": bool}
          {"type": "token",       "content": str}
          {"type": "done",        "message_id": str, "usage": dict}
          {"type": "error",       "message": str}

        Flow:
          1. Build context with enable_tools=True
          2. Call chat_completion() with tool definitions
          3. If finish_reason == "tool_calls": execute, append results, repeat
          4. On final text response: chunk-emit as tokens, save to DB
        """
        from app.ai.tools import tool_executor, tool_registry

        tool_defs = tool_registry.get_tool_definitions()
        messages = await self._build_context(
            conversation, user_message, enable_tools=True
        )

        # Auto-route to the correct provider based on the model id
        provider, resolved_model = get_provider_for_model(model)

        full_content = ""
        all_tool_calls_used: list[dict] = []
        start = time.monotonic()

        for round_num in range(settings.TOOLS_MAX_ROUNDS):
            try:
                completion = await provider.chat_completion(
                    messages=messages,
                    model=resolved_model,
                    tools=tool_defs,
                )
            except Exception as e:
                logger.error(
                    "chat_service.tool_round_error",
                    round=round_num,
                    error=str(e),
                )
                yield {"type": "error", "message": str(e)}
                return

            # ── Tool call round ──────────────────────────────────────────────
            if completion.finish_reason == "tool_calls" and completion.tool_calls:
                logger.info(
                    "chat_service.tool_calls_detected",
                    round=round_num,
                    tool_count=len(completion.tool_calls),
                )

                # Append the assistant's tool-call request to the context
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content="",
                        tool_calls=completion.tool_calls,
                    )
                )

                for tc in completion.tool_calls:
                    import json as _json
                    try:
                        input_args = _json.loads(tc.get("arguments", "{}"))
                    except Exception:
                        input_args = {}

                    # Emit tool_use event so frontend can show spinner
                    yield {
                        "type": "tool_use",
                        "tool_name": tc["name"],
                        "input": input_args,
                    }

                    # Execute the tool
                    result = await tool_executor.execute_from_call(tc)
                    all_tool_calls_used.append({
                        "name": tc["name"],
                        "is_error": result.is_error,
                    })

                    # Emit tool_result event
                    yield {
                        "type": "tool_result",
                        "tool_name": tc["name"],
                        "result": result.content,
                        "is_error": result.is_error,
                    }

                    # Append tool result to context for next round
                    messages.append(
                        ChatMessage(
                            role="tool",
                            content=result.content,
                            name=tc["name"],
                            tool_call_id=tc["id"],
                        )
                    )

                # Continue to next round
                continue

            # ── Final text response ──────────────────────────────────────────
            full_content = completion.content

            # Chunk-emit the final text so the frontend streams it
            for i in range(0, len(full_content), _CHUNK_SIZE):
                chunk = full_content[i : i + _CHUNK_SIZE]
                yield {"type": "token", "content": chunk}
                if i + _CHUNK_SIZE < len(full_content):
                    await asyncio.sleep(_CHUNK_SLEEP_S)

            break  # done

        else:
            # Exhausted all rounds without a final text response
            logger.warning(
                "chat_service.tool_max_rounds_exceeded",
                max_rounds=settings.TOOLS_MAX_ROUNDS,
            )
            fallback = "I reached the maximum number of tool-calling steps. Please try rephrasing your question."
            full_content = fallback
            for i in range(0, len(fallback), _CHUNK_SIZE):
                yield {"type": "token", "content": fallback[i : i + _CHUNK_SIZE]}

        # Save assistant response
        latency_ms = int((time.monotonic() - start) * 1000)
        assistant_msg = await self.save_assistant_message(
            conversation_id=conversation.id,
            user_id=user_id,
            content=full_content,
            metadata={"tools_used": all_tool_calls_used} if all_tool_calls_used else {},
        )

        # Record generation (token counts are estimates for tool-round completions)
        from app.utils.tokens import count_tokens
        prompt_text = " ".join(m.content for m in messages if m.content)
        prompt_tokens = count_tokens(prompt_text, resolved_model)
        completion_tokens = count_tokens(full_content, resolved_model)

        final_completion = CompletionResponse(
            content=full_content,
            model=resolved_model,
            provider=provider.provider_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            finish_reason="stop",
            latency_ms=latency_ms,
        )
        await self.record_generation(assistant_msg.id, conversation.id, final_completion)

        # Commit before yielding done so immediate frontend refetch sees saved messages.
        await self.db.commit()

        yield {
            "type": "done",
            "message_id": str(assistant_msg.id),
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "latency_ms": latency_ms,
                "tools_used": all_tool_calls_used,
            },
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Public chat entry points
    # ──────────────────────────────────────────────────────────────────────────

    async def chat_stream(
        self,
        conversation: Conversation,
        user_message: str,
        user_id: UUID,
        existing_user_msg: "Message | None" = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Main streaming chat pipeline.

        Yields dicts with type:
          {"type": "token",       "content": "..."}
          {"type": "tool_use",    "tool_name": "...", "input": {...}}
          {"type": "tool_result", "tool_name": "...", "result": "...", "is_error": bool}
          {"type": "done",        "message_id": "...", "usage": {...}}
          {"type": "error",       "message": "..."}

        Pass `existing_user_msg` to skip saving a new user message (e.g. regenerate path).
        """
        # 1. Save user message (skip if regenerating from an existing one)
        if existing_user_msg is not None:
            user_msg = existing_user_msg
        else:
            user_msg = await self.save_user_message(
                conversation_id=conversation.id,
                user_id=user_id,
                content=user_message,
            )

        model = conversation.model

        # 2. Route to tool-calling or direct streaming path.
        # Only use the tool loop for models that actually support function calling.
        from app.ai.providers.router import MODEL_REGISTRY
        model_info = next((m for m in MODEL_REGISTRY if m.id == model), None)
        model_supports_tools = model_info.supports_tools if model_info else True

        if settings.TOOLS_ENABLED and model_supports_tools:
            async for event in self._chat_with_tools(
                conversation=conversation,
                user_message=user_message,
                user_id=user_id,
                model=model,
            ):
                if event["type"] == "done":
                    self._trigger_background_tasks_by_id(
                        conversation, user_msg, event
                    )
                yield event
            return

        # ── Direct streaming path (no tools) ────────────────────────────────
        messages = await self._build_context(conversation, user_message)

        provider, resolved_model = get_provider_for_model(model)

        full_content = ""
        start = time.monotonic()

        try:
            async for token in provider.stream_completion(
                messages=messages,
                model=resolved_model,
            ):
                full_content += token
                yield {"type": "token", "content": token}

        except Exception as e:
            logger.error(
                "chat_service.stream_error",
                error=str(e),
                conversation_id=str(conversation.id),
            )
            yield {"type": "error", "message": str(e)}
            return

        latency_ms = int((time.monotonic() - start) * 1000)

        assistant_msg = await self.save_assistant_message(
            conversation_id=conversation.id,
            user_id=user_id,
            content=full_content,
        )

        from app.utils.tokens import count_tokens
        prompt_text = " ".join(m.content or "" for m in messages)
        prompt_tokens = count_tokens(prompt_text, resolved_model)
        completion_tokens = count_tokens(full_content, resolved_model)

        completion = CompletionResponse(
            content=full_content,
            model=resolved_model,
            provider=provider.provider_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            finish_reason="stop",
            latency_ms=latency_ms,
        )
        await self.record_generation(assistant_msg.id, conversation.id, completion)

        # Commit BEFORE yielding done so the frontend's immediate refetch
        # sees the committed messages rather than the in-progress transaction.
        await self.db.commit()

        self._trigger_background_tasks(conversation, user_msg, full_content)

        yield {
            "type": "done",
            "message_id": str(assistant_msg.id),
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "latency_ms": latency_ms,
            },
        }

    def _trigger_background_tasks_by_id(
        self,
        conversation: Conversation,
        user_msg: Message,
        done_event: dict,
    ) -> None:
        """
        Variant of _trigger_background_tasks used after the tool loop,
        where we only have the done event dict (not the assistant Message object).
        """
        try:
            from app.workers.tasks.title_generation import generate_title_task
            from app.workers.tasks.memory_extraction import extract_memory_task

            if conversation.title == "New Chat" and conversation.message_count <= 2:
                generate_title_task.delay(str(conversation.id), user_msg.content)

            ai_response_approx = done_event.get("usage", {}).get("completion_tokens", 0)
            if settings.MEMORY_EXTRACTION_ENABLED and ai_response_approx > 30:
                extract_memory_task.delay(
                    str(conversation.user_id),
                    str(conversation.id),
                    user_msg.content,
                    "",  # full text not available here; memory extraction will be approximate
                )
        except Exception as e:
            logger.warning("chat_service.background_task_error", error=str(e))

    def _trigger_background_tasks(
        self,
        conversation: Conversation,
        user_msg: Message,
        ai_response: str,
    ) -> None:
        """
        Fire-and-forget background tasks.
        These run async and don't block the chat response.

        Why background:
        - Title generation: only needed once, on first message
        - Memory extraction: valuable but not time-critical
        - Summarization: only when threshold reached
        """
        try:
            from app.workers.tasks.title_generation import generate_title_task
            from app.workers.tasks.memory_extraction import extract_memory_task

            # Generate title only if still "New Chat"
            if conversation.title == "New Chat" and conversation.message_count <= 2:
                generate_title_task.delay(
                    str(conversation.id),
                    user_msg.content,
                )

            # Extract memory from meaningful exchanges
            if settings.MEMORY_EXTRACTION_ENABLED and len(ai_response) > 100:
                extract_memory_task.delay(
                    str(conversation.user_id),
                    str(conversation.id),
                    user_msg.content,
                    ai_response,
                )

        except Exception as e:
            # Background task failures must never break the main chat flow
            logger.warning("chat_service.background_task_error", error=str(e))

    async def chat_complete(
        self,
        conversation: Conversation,
        user_message: str,
        user_id: UUID,
    ) -> tuple[Message, CompletionResponse]:
        """
        Non-streaming chat — returns complete response.
        Used for: API integrations, testing.
        """
        await self.save_user_message(conversation.id, user_id, user_message)
        messages = await self._build_context(conversation, user_message)

        provider, resolved_model = get_provider_for_model(conversation.model)

        completion = await provider.chat_completion(messages=messages, model=resolved_model)
        assistant_msg = await self.save_assistant_message(
            conversation.id, user_id, completion.content
        )
        await self.record_generation(assistant_msg.id, conversation.id, completion)
        self._trigger_background_tasks(conversation, assistant_msg, completion.content)

        return assistant_msg, completion
