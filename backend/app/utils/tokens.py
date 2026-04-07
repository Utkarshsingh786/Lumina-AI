"""
Token counting utilities using tiktoken.

Why token awareness matters:
- LLMs have hard context limits — exceeding them causes errors or truncation
- Token cost is linear — needlessly large contexts are expensive
- Good context management is what separates toy demos from real products

Strategy:
- Count tokens before sending to AI
- Reserve CONTEXT_RESERVE_TOKENS for the response
- Trim oldest messages first (sliding window) when over budget
- Replace trimmed messages with their summary if available
"""

from functools import lru_cache

import tiktoken

from app.core.logging import get_logger

logger = get_logger(__name__)

# Model to encoding mapping — update as new models release
MODEL_ENCODING: dict[str, str] = {
    "gpt-4o": "o200k_base",
    "gpt-4o-mini": "o200k_base",
    "gpt-4-turbo": "cl100k_base",
    "gpt-4": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
}
DEFAULT_ENCODING = "o200k_base"


@lru_cache(maxsize=4)
def get_encoding(model: str) -> tiktoken.Encoding:
    """Cached encoding — don't reload on every request."""
    encoding_name = MODEL_ENCODING.get(model, DEFAULT_ENCODING)
    return tiktoken.get_encoding(encoding_name)


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens in a string for a given model."""
    try:
        enc = get_encoding(model)
        return len(enc.encode(text))
    except Exception:
        # Fallback: rough estimate (1 token ≈ 4 chars)
        return len(text) // 4


def count_message_tokens(role: str, content: str, model: str = "gpt-4o") -> int:
    """
    Count tokens for a single message including role overhead.
    OpenAI adds ~4 tokens per message for formatting.
    """
    return count_tokens(content, model) + 4  # role + formatting overhead


def count_messages_tokens(
    messages: list[dict[str, str]], model: str = "gpt-4o"
) -> int:
    """Count total tokens for a list of {role, content} dicts."""
    total = 3  # OpenAI adds 3 tokens for conversation structure
    for msg in messages:
        total += count_message_tokens(msg["role"], msg["content"], model)
    return total
