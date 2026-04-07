"""
Anthropic (Claude) provider implementation.

Key differences from OpenAI to handle:
- System prompt is a top-level field, not a message role
- Tool format differs (input_schema vs parameters)
- Streaming uses different event types
- No direct embedding API — requires OpenAI or a separate embedding service

Strategy for embeddings: fall back to OpenAI embeddings if Anthropic is the chat provider.
This is fine — embeddings don't need to come from the same provider as chat.
"""

import time
from collections.abc import AsyncGenerator
from typing import Any

import anthropic
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.ai.providers.base import (
    BaseAIProvider,
    ChatMessage,
    CompletionResponse,
    ToolDefinition,
)
from app.core.config import settings
from app.core.exceptions import AIProviderError
from app.core.logging import get_logger

logger = get_logger(__name__)

ANTHROPIC_PRICING: dict[str, dict[str, float]] = {
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
}


class AnthropicProvider(BaseAIProvider):
    provider_name = "anthropic"

    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=60.0,
            max_retries=0,
        )

    def _get_fast_model(self) -> str:
        return "claude-3-5-haiku-20241022"

    def _split_system_and_messages(
        self, messages: list[ChatMessage]
    ) -> tuple[str, list[dict]]:
        """
        Anthropic requires system prompt separate from messages.
        Extract system messages and combine into single system string.

        Tool call format differences from OpenAI:
        - Assistant tool use: content block list with type="tool_use"
        - Tool results: role="user" with type="tool_result" content blocks
        - Multiple tool results for the same turn are batched into one user message
        """
        import json as _json

        system_parts = []
        chat_messages = []
        pending_tool_results: list[dict] = []

        def flush_tool_results() -> None:
            if pending_tool_results:
                chat_messages.append({"role": "user", "content": list(pending_tool_results)})
                pending_tool_results.clear()

        for msg in messages:
            if msg.role == "system":
                flush_tool_results()
                system_parts.append(msg.content)

            elif msg.tool_calls:
                # Assistant message requesting tool calls
                flush_tool_results()
                chat_messages.append({
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["name"],
                            "input": _json.loads(tc["arguments"]),
                        }
                        for tc in msg.tool_calls
                    ],
                })

            elif msg.role == "tool":
                # Tool result — batch into pending list (flushed when we see a non-tool msg)
                pending_tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,
                    "content": msg.content,
                })

            else:
                flush_tool_results()
                chat_messages.append({"role": msg.role, "content": msg.content})

        flush_tool_results()
        return "\n\n".join(system_parts), chat_messages

    def _to_anthropic_tools(self, tools: list[ToolDefinition]) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tools
        ]

    def _estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        if model not in ANTHROPIC_PRICING:
            return 0.0
        pricing = ANTHROPIC_PRICING[model]
        return (
            prompt_tokens / 1_000_000 * pricing["input"]
            + completion_tokens / 1_000_000 * pricing["output"]
        )

    @retry(
        retry=retry_if_exception_type(anthropic.RateLimitError),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    async def chat_completion(
        self,
        messages: list[ChatMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: list[ToolDefinition] | None = None,
    ) -> CompletionResponse:
        start = time.monotonic()
        system, chat_messages = self._split_system_and_messages(messages)

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = self._to_anthropic_tools(tools)

        try:
            response = await self.client.messages.create(**kwargs)
        except anthropic.RateLimitError:
            logger.warning("anthropic.rate_limit", model=model)
            raise
        except anthropic.APIStatusError as e:
            raise AIProviderError(f"Anthropic API error {e.status_code}: {e.message}")

        latency_ms = int((time.monotonic() - start) * 1000)
        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content = block.text
                break

        return CompletionResponse(
            content=content,
            model=response.model,
            provider=self.provider_name,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            finish_reason=response.stop_reason or "end_turn",
            latency_ms=latency_ms,
            cost_usd=self._estimate_cost(
                model, response.usage.input_tokens, response.usage.output_tokens
            ),
        )

    async def stream_completion(
        self,
        messages: list[ChatMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: list[ToolDefinition] | None = None,  # noqa: ARG002 — unused by design (see OpenAI provider note)
    ) -> AsyncGenerator[str, None]:
        system, chat_messages = self._split_system_and_messages(messages)
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system

        try:
            async with self.client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
        except anthropic.APIStatusError as e:
            raise AIProviderError(f"Anthropic stream error: {e.message}")

    async def generate_embeddings(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """
        Anthropic doesn't offer embeddings — delegate to OpenAI.
        This is explicitly acceptable; embedding and chat providers can differ.
        """
        from app.ai.providers.openai_provider import OpenAIProvider
        fallback = OpenAIProvider()
        return await fallback.generate_embeddings(texts, model)
