"""
Google Gemini provider — accesses Gemini models via OpenAI-compatible API.

Setup:
  1. Go to https://aistudio.google.com/app/apikey
  2. Create an API key (free tier: 15 RPM, 1M TPM on Flash)
  3. Set GEMINI_API_KEY=AIza... in backend/.env

Gemini exposes an OpenAI-compatible endpoint since late 2024:
  https://generativelanguage.googleapis.com/v1beta/openai/

This means we reuse the openai Python client with a custom base_url.
No SDK dependency on google-generativeai needed.

Supported models (as of 2025):
  gemini-2.0-flash          — fastest, 1M context, multimodal, tool support
  gemini-2.0-flash-lite     — cheapest, 1M context, tool support
  gemini-1.5-pro            — highest quality, 2M context, tool support
  gemini-1.5-flash          — fast + smart, 1M context, tool support
  gemini-1.5-flash-8b       — very fast, small, 1M context

Embeddings: text-embedding-004 (768 dims, available on free tier).
WARNING: if your pgvector index was created with 1536 dims (OpenAI default),
RAG will not work with Gemini embeddings — run backend/migrations/update_embed_dims.sql
or keep an OpenAI key configured for embeddings only.

Pricing (as of 2025): https://ai.google.dev/pricing
  gemini-2.0-flash:       $0.075/1M input,  $0.30/1M output
  gemini-1.5-pro:         $1.25/1M input,   $5.00/1M output (>128k: 2.5x)
  gemini-1.5-flash:       $0.075/1M input,  $0.30/1M output
  text-embedding-004:     free on AI Studio (rate limited)
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

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# Per-model pricing (input, output) per million tokens
_PRICING: dict[str, tuple[float, float]] = {
    "gemini-2.0-flash":           (0.075, 0.30),
    "gemini-2.0-flash-lite":      (0.075, 0.30),
    "gemini-1.5-pro":             (1.25,  5.00),
    "gemini-1.5-flash":           (0.075, 0.30),
    "gemini-1.5-flash-8b":        (0.0375, 0.15),
}


def _compute_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate USD cost using published Gemini pricing."""
    inp, out = _PRICING.get(model, (0.0, 0.0))
    return (prompt_tokens * inp + completion_tokens * out) / 1_000_000


class GeminiProvider(BaseAIProvider):
    provider_name = "gemini"

    def __init__(self) -> None:
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(
            base_url=_GEMINI_BASE_URL,
            api_key=settings.GEMINI_API_KEY,
            timeout=120.0,
            max_retries=1,
        )
        self.embed_model = settings.GEMINI_EMBED_MODEL

    def _get_fast_model(self) -> str:
        return settings.GEMINI_DEFAULT_MODEL

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
                            "function": {
                                "name": tc["name"],
                                "arguments": tc["arguments"],
                            },
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
                "Gemini rate limit reached. Free tier: 15 RPM / 1M TPM. "
                "See https://ai.google.dev/pricing for quotas."
            ) from e
        except APIStatusError as e:
            if e.status_code in (400, 401, 403):
                raise AIProviderError(
                    f"Gemini auth/config error ({e.status_code}). "
                    "Check GEMINI_API_KEY in backend/.env"
                ) from e
            raise AIProviderError(f"Gemini error {e.status_code}: {e.message}") from e
        except APIConnectionError as e:
            raise AITimeoutError("Gemini connection timeout") from e

        latency_ms = int((time.monotonic() - start) * 1000)
        choice = response.choices[0]
        usage = response.usage

        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        cost = _compute_cost(model, prompt_tokens, completion_tokens)

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
            model=model,
            provider=self.provider_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
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
            raise AIProviderError(f"Gemini stream error: {e.message}") from e
        except APIConnectionError as e:
            raise AITimeoutError("Gemini stream connection lost") from e

    async def generate_embeddings(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        from openai import APIConnectionError, APIStatusError

        embed_model = model or self.embed_model
        try:
            response = await self.client.embeddings.create(
                input=texts,
                model=embed_model,
            )
            return [item.embedding for item in response.data]
        except APIConnectionError as e:
            raise AIProviderError(
                "Cannot connect to Gemini embeddings endpoint."
            ) from e
        except APIStatusError as e:
            raise AIProviderError(f"Gemini embedding error: {e.message}") from e
