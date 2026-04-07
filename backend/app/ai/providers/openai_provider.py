"""
OpenAI provider implementation.

Handles:
- chat completions (streaming + non-streaming)
- embeddings
- token counting via tiktoken
- cost estimation
- structured error mapping to our exception hierarchy

Retry strategy: tenacity with exponential backoff on rate limits and transient errors.
We do NOT retry on authentication errors or content policy violations.
"""

import time
from collections.abc import AsyncGenerator
from typing import Any

from openai import AsyncOpenAI, APIConnectionError, APIStatusError, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.ai.providers.base import (
    BaseAIProvider,
    ChatMessage,
    CompletionResponse,
    ToolDefinition,
)
from app.core.config import settings
from app.core.exceptions import AIProviderError, AITimeoutError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Cost per 1M tokens (USD) — update as OpenAI changes pricing
OPENAI_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "o1-preview": {"input": 15.00, "output": 60.00},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
    "text-embedding-3-large": {"input": 0.13, "output": 0.0},
}


class OpenAIProvider(BaseAIProvider):
    provider_name = "openai"

    def __init__(self) -> None:
        client_kwargs: dict = {
            "api_key": settings.OPENAI_API_KEY,
            "timeout": 60.0,
            "max_retries": 0,  # we handle retries ourselves with tenacity
        }
        if settings.OPENAI_ORG_ID:
            client_kwargs["organization"] = settings.OPENAI_ORG_ID
        self.client = AsyncOpenAI(**client_kwargs)

    def _get_fast_model(self) -> str:
        return settings.DEFAULT_FAST_MODEL

    def _to_openai_messages(self, messages: list[ChatMessage]) -> list[dict]:
        """Convert our normalized format to OpenAI's message format."""
        result = []
        for msg in messages:
            if msg.tool_calls:
                # Assistant message that requested tool calls — content must be null
                m: dict[str, Any] = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": tc["arguments"]},
                        }
                        for tc in msg.tool_calls
                    ],
                }
            else:
                m = {"role": msg.role, "content": msg.content}
                if msg.name:
                    m["name"] = msg.name
                if msg.tool_call_id:
                    m["tool_call_id"] = msg.tool_call_id
            result.append(m)
        return result

    def _to_openai_tools(self, tools: list[ToolDefinition]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    def _estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        if model not in OPENAI_PRICING:
            return 0.0
        pricing = OPENAI_PRICING[model]
        return (
            prompt_tokens / 1_000_000 * pricing["input"]
            + completion_tokens / 1_000_000 * pricing["output"]
        )

    @retry(
        retry=retry_if_exception_type(APIConnectionError),
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
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._to_openai_messages(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = self._to_openai_tools(tools)
            kwargs["tool_choice"] = "auto"

        try:
            response = await self.client.chat.completions.create(**kwargs)
        except RateLimitError:
            logger.warning("openai.rate_limit", model=model)
            raise AIProviderError("OpenAI rate limit reached — please wait a moment and try again")
        except APIStatusError as e:
            if e.status_code in (401, 403):
                raise AIProviderError(f"OpenAI auth error: {e.message}")
            raise AIProviderError(f"OpenAI API error {e.status_code}: {e.message}")
        except APIConnectionError:
            raise AITimeoutError("OpenAI connection timeout")

        latency_ms = int((time.monotonic() - start) * 1000)
        choice = response.choices[0]
        usage = response.usage

        # Extract tool calls if present
        tool_calls = None
        if choice.message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
                for tc in choice.message.tool_calls
            ]

        return CompletionResponse(
            content=choice.message.content or "",
            model=response.model,
            provider=self.provider_name,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            finish_reason=choice.finish_reason or "stop",
            latency_ms=latency_ms,
            cost_usd=self._estimate_cost(model, usage.prompt_tokens, usage.completion_tokens),
            tool_calls=tool_calls,
        )

    async def stream_completion(
        self,
        messages: list[ChatMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: list[ToolDefinition] | None = None,  # noqa: ARG002 — unused by design
    ) -> AsyncGenerator[str, None]:
        """
        Yields raw token strings as they arrive from the API.
        The caller assembles them and handles SSE formatting.

        Note: `tools` is intentionally unused here. The agentic tool loop
        uses chat_completion() (non-streaming) for tool rounds, then emits
        the final text response as chunked tokens from ChatService. This
        avoids the complexity of accumulating streamed tool-call argument
        deltas from the OpenAI streaming protocol.
        """
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._to_openai_messages(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            stream = await self.client.chat.completions.create(stream=True, **kwargs)
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except APIStatusError as e:
            raise AIProviderError(f"OpenAI stream error: {e.message}")
        except APIConnectionError:
            raise AITimeoutError("OpenAI stream connection lost")

    async def generate_embeddings(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        embed_model = model or settings.DEFAULT_EMBED_MODEL
        try:
            response = await self.client.embeddings.create(
                input=texts,
                model=embed_model,
            )
            return [item.embedding for item in response.data]
        except APIStatusError as e:
            raise AIProviderError(f"OpenAI embedding error: {e.message}")
