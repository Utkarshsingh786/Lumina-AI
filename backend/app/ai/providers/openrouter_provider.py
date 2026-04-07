"""
OpenRouter provider — access hundreds of AI models via a single API.

Free models available (as of 2025): these have `:free` suffix and cost $0.
  mistralai/mistral-7b-instruct:free
  meta-llama/llama-3.2-3b-instruct:free
  meta-llama/llama-3.1-8b-instruct:free
  google/gemma-2-9b-it:free
  microsoft/phi-3-mini-128k-instruct:free
  qwen/qwen-2-7b-instruct:free

Setup:
  1. Sign up at https://openrouter.ai (free account, no credit card)
  2. Create an API key at https://openrouter.ai/keys
  3. Set OPENROUTER_API_KEY=sk-or-... in backend/.env

OpenRouter uses the OpenAI-compatible API, so we reuse the openai client
with a custom base_url and add the required HTTP-Referer header.

Note: OpenRouter does NOT support embeddings. If you use OpenRouter as your
chat provider, set OPENAI_API_KEY for embeddings (RAG) or disable RAG.
"""

import time
from collections.abc import AsyncGenerator
from typing import Any

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


class OpenRouterProvider(BaseAIProvider):
    provider_name = "openrouter"

    def __init__(self) -> None:
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(
            base_url=settings.OPENROUTER_BASE_URL,
            api_key=settings.OPENROUTER_API_KEY,
            default_headers={
                # Required by OpenRouter for attribution and rate limit tiers
                "HTTP-Referer": "https://lumina.app",
                "X-Title": "Lumina AI",
            },
            timeout=60.0,
            max_retries=1,
        )

    def _get_fast_model(self) -> str:
        # Fast free model for title gen / summaries
        return "nvidia/nemotron-3-nano-30b-a3b:free"

    def _to_messages(self, messages: list[ChatMessage]) -> list[dict]:
        result = []
        for msg in messages:
            if msg.tool_calls:
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

    def _to_tools(self, tools: list[ToolDefinition]) -> list[dict]:
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

    async def chat_completion(
        self,
        messages: list[ChatMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: list[ToolDefinition] | None = None,
    ) -> CompletionResponse:
        from openai import APIConnectionError, APIStatusError, RateLimitError

        start = time.monotonic()
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._to_messages(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = self._to_tools(tools)
            kwargs["tool_choice"] = "auto"

        try:
            response = await self.client.chat.completions.create(**kwargs)
        except RateLimitError as e:
            raise AIProviderError(
                "OpenRouter rate limit reached. Free tier allows limited requests per minute. "
                "Try again shortly or upgrade at https://openrouter.ai"
            ) from e
        except APIStatusError as e:
            if e.status_code in (401, 403):
                raise AIProviderError(
                    "OpenRouter auth error. Check OPENROUTER_API_KEY in backend/.env"
                ) from e
            raise AIProviderError(f"OpenRouter error {e.status_code}: {e.message}") from e
        except APIConnectionError as e:
            raise AITimeoutError("OpenRouter connection timeout") from e

        latency_ms = int((time.monotonic() - start) * 1000)
        choice = response.choices[0]
        usage = response.usage

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

        # OpenRouter reports usage; free models cost $0
        cost = 0.0
        if usage and hasattr(usage, "total_cost"):
            cost = float(usage.total_cost or 0)

        return CompletionResponse(
            content=choice.message.content or "",
            model=model,
            provider=self.provider_name,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            finish_reason=choice.finish_reason or "stop",
            latency_ms=latency_ms,
            cost_usd=cost,
            tool_calls=tool_calls,
        )

    async def stream_completion(
        self,
        messages: list[ChatMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncGenerator[str, None]:
        from openai import APIConnectionError, APIStatusError

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._to_messages(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            stream = await self.client.chat.completions.create(stream=True, **kwargs)
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except APIStatusError as e:
            raise AIProviderError(f"OpenRouter stream error: {e.message}") from e
        except APIConnectionError as e:
            raise AITimeoutError("OpenRouter stream connection lost") from e

    async def generate_embeddings(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        # OpenRouter does not provide an embeddings API.
        # The RAG retriever catches this and falls back gracefully.
        raise AIProviderError(
            "OpenRouter does not support embeddings. "
            "Set OPENAI_API_KEY in backend/.env to enable RAG, "
            "or use Ollama with nomic-embed-text for local embeddings."
        )
