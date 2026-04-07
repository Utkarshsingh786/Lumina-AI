"""
Ollama provider — runs AI models 100% locally at no cost.

Setup:
  1. Install Ollama: https://ollama.com/download
  2. Pull a model: ollama pull llama3.2
  3. Set OLLAMA_ENABLED=true in backend/.env
  4. Set OLLAMA_BASE_URL=http://localhost:11434 (default)

Ollama exposes an OpenAI-compatible /v1 API since v0.1.14, so we reuse
the openai Python client with a custom base_url. No API key needed
(the client requires a value, but Ollama ignores it).

Tool calling is supported for: llama3.1, llama3.2, mistral, mistral-nemo,
qwen2.5, firefunction-v2. Other models will fall back to text-only responses.

Embeddings: uses nomic-embed-text (768 dims) or mxbai-embed-large (1024 dims).
WARNING: if your pgvector index was created with 1536 dims (OpenAI default),
RAG will not work with Ollama embeddings — run backend/migrations/update_embed_dims.sql
or keep OpenAI key configured for embeddings only.
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


class OllamaProvider(BaseAIProvider):
    provider_name = "ollama"

    def __init__(self) -> None:
        # Import here so the dependency is optional — if openai isn't installed
        # and Ollama isn't used, startup still works.
        from openai import AsyncOpenAI

        base_url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/v1"
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key="ollama",        # required by client, ignored by Ollama
            timeout=120.0,           # longer timeout for local inference
            max_retries=1,
        )
        self.embed_model = settings.OLLAMA_EMBED_MODEL

    def _get_fast_model(self) -> str:
        return settings.OLLAMA_DEFAULT_MODEL

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
        from openai import APIConnectionError, APIStatusError

        start = time.monotonic()
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._to_messages(messages),
            "temperature": temperature,
        }
        # Ollama ignores max_tokens if set to 0; use -1 for unlimited
        if max_tokens > 0:
            kwargs["max_tokens"] = max_tokens

        if tools:
            kwargs["tools"] = self._to_tools(tools)
            kwargs["tool_choice"] = "auto"

        try:
            response = await self.client.chat.completions.create(**kwargs)
        except APIConnectionError as e:
            raise AIProviderError(
                f"Cannot connect to Ollama at {settings.OLLAMA_BASE_URL}. "
                "Is Ollama running? Try: ollama serve"
            ) from e
        except APIStatusError as e:
            raise AIProviderError(f"Ollama error {e.status_code}: {e.message}") from e

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

        return CompletionResponse(
            content=choice.message.content or "",
            model=model,
            provider=self.provider_name,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            finish_reason=choice.finish_reason or "stop",
            latency_ms=latency_ms,
            cost_usd=0.0,   # local — always free
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
            "temperature": temperature,
        }
        if max_tokens > 0:
            kwargs["max_tokens"] = max_tokens

        try:
            stream = await self.client.chat.completions.create(stream=True, **kwargs)
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except APIConnectionError as e:
            raise AIProviderError(
                f"Cannot connect to Ollama at {settings.OLLAMA_BASE_URL}. "
                "Is Ollama running? Try: ollama serve"
            ) from e
        except APIStatusError as e:
            raise AIProviderError(f"Ollama stream error: {e.message}") from e

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
                f"Cannot connect to Ollama at {settings.OLLAMA_BASE_URL} for embeddings."
            ) from e
        except APIStatusError as e:
            raise AIProviderError(f"Ollama embedding error: {e.message}") from e
