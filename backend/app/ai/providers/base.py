"""
Abstract AI provider interface.

Why this abstraction:
- Vendor-agnostic: swap OpenAI for Anthropic/Groq without changing service code
- Each provider implements the same contract
- Model routing (fast/reasoning/embedding) handled by the router, not services
- Retry/timeout/fallback logic lives in one place

Every provider must implement these methods:
    chat_completion()     → full response, for simple cases
    stream_completion()   → async generator of tokens
    generate_embeddings() → vector representations
    generate_title()      → fast cheap call for conversation titles
    summarize()           → condense long conversation segments

What to add later:
- generate_image()       → DALL-E / Stable Diffusion
- transcribe_audio()     → Whisper / ElevenLabs
- function_calling()     → more structured tool protocol handling
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any


@dataclass
class ChatMessage:
    """Normalized message format — all providers accept this."""
    role: str   # system | user | assistant | tool
    content: str
    name: str | None = None          # for tool result messages
    tool_call_id: str | None = None  # for tool result messages (links result back to call)
    # Populated on assistant messages when the model requested tool calls.
    # Each entry: {"id": str, "name": str, "arguments": str (JSON)}
    tool_calls: list[dict] | None = None


@dataclass
class CompletionResponse:
    """Normalized completion response."""
    content: str
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    finish_reason: str
    latency_ms: int
    cost_usd: float | None = None
    tool_calls: list[dict] | None = None


@dataclass
class ToolDefinition:
    """Provider-agnostic tool schema."""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema object


class BaseAIProvider(ABC):
    """
    Abstract base for all AI providers.
    Concrete implementations live in openai_provider.py, anthropic_provider.py, etc.
    """

    provider_name: str = "base"

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[ChatMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: list[ToolDefinition] | None = None,
    ) -> CompletionResponse:
        """Single full response — use for background tasks like title gen, summaries."""
        ...

    @abstractmethod
    async def stream_completion(
        self,
        messages: list[ChatMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Async generator yielding raw token strings.
        Caller is responsible for assembling the full response.
        """
        ...

    @abstractmethod
    async def generate_embeddings(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate vector embeddings for RAG/memory semantic search."""
        ...

    async def generate_title(self, first_message: str, model: str | None = None) -> str:
        """
        Generate a short conversation title from the first user message.
        Default implementation uses chat_completion with a fast model.
        Override in providers that have cheaper title-specific endpoints.
        """
        from app.ai.prompts.system import TITLE_GENERATION_PROMPT

        response = await self.chat_completion(
            messages=[
                ChatMessage(role="system", content=TITLE_GENERATION_PROMPT),
                ChatMessage(role="user", content=first_message[:500]),
            ],
            model=model or self._get_fast_model(),
            max_tokens=30,
            temperature=0.3,
        )
        # Strip quotes that models sometimes add
        return response.content.strip().strip('"\'').strip()[:100]

    async def summarize_conversation(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
    ) -> str:
        """
        Summarize a list of messages into a compact narrative.
        Used for conversation compression when context window fills up.
        """
        from app.ai.prompts.system import SUMMARIZATION_PROMPT

        formatted = "\n".join(
            f"{m.role.upper()}: {m.content[:500]}" for m in messages
        )
        response = await self.chat_completion(
            messages=[
                ChatMessage(role="system", content=SUMMARIZATION_PROMPT),
                ChatMessage(role="user", content=formatted),
            ],
            model=model or self._get_fast_model(),
            max_tokens=500,
            temperature=0.3,
        )
        return response.content

    def _get_fast_model(self) -> str:
        """Override in subclasses to return provider's fast/cheap model."""
        raise NotImplementedError(f"{self.provider_name} must define _get_fast_model()")
