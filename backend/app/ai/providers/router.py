"""
AI provider and model router.

The MODEL_REGISTRY is the single source of truth for every model the app
knows about. Each entry declares:
  - which provider handles it
  - what tier it is (best / fast / embedding)
  - whether it's free
  - a human-readable name and description

Resolution order when the user picks a model from the UI:
  1. Look up the model in MODEL_REGISTRY → get provider name
  2. Instantiate (or reuse cached) provider
  3. Pass model id to provider.chat_completion / stream_completion

Adding a new provider or model only requires:
  a) A new provider file in app/ai/providers/
  b) A new entry in get_provider() below
  c) New entries in MODEL_REGISTRY

No other file needs to change.
"""

from enum import StrEnum
from functools import lru_cache
from dataclasses import dataclass

from app.ai.providers.base import BaseAIProvider
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class TaskType(StrEnum):
    CHAT = "chat"
    FAST = "fast"          # title gen, quick classification
    REASONING = "reasoning"
    EMBEDDING = "embedding"
    SUMMARIZATION = "summarization"


@dataclass
class ModelInfo:
    """All metadata about a single model — used by the /health/models endpoint."""
    id: str
    name: str
    provider: str
    tier: str              # best | fast | embedding
    is_free: bool = False
    context_window: int = 128_000
    description: str = ""
    supports_tools: bool = True


# ── Model Registry ───────────────────────────────────────────────────────────
# Every model the app knows about. Provider is inferred from this table —
# chat_service and the health endpoint both read from here.

MODEL_REGISTRY: list[ModelInfo] = [
    # ── OpenAI ──────────────────────────────────────────────────────────
    ModelInfo(
        id="gpt-4o",
        name="GPT-4o",
        provider="openai",
        tier="best",
        context_window=128_000,
        description="Most capable OpenAI model. Best for complex reasoning.",
        supports_tools=True,
    ),
    ModelInfo(
        id="gpt-4o-mini",
        name="GPT-4o mini",
        provider="openai",
        tier="fast",
        context_window=128_000,
        description="Fast and cheap. Great for everyday tasks.",
        supports_tools=True,
    ),

    # ── Anthropic ────────────────────────────────────────────────────────
    ModelInfo(
        id="claude-3-5-sonnet-20241022",
        name="Claude 3.5 Sonnet",
        provider="anthropic",
        tier="best",
        context_window=200_000,
        description="Anthropic's smartest model. Excellent at coding and analysis.",
        supports_tools=True,
    ),
    ModelInfo(
        id="claude-3-5-haiku-20241022",
        name="Claude 3.5 Haiku",
        provider="anthropic",
        tier="fast",
        context_window=200_000,
        description="Fast and affordable Anthropic model.",
        supports_tools=True,
    ),

    # ── OpenRouter — Free Models ──────────────────────────────────────────
    # These :free models are $0 and require only a free OpenRouter account.
    # List last verified: 2026-04-06 via https://openrouter.ai/api/v1/models
    ModelInfo(
        id="qwen/qwen3.6-plus:free",
        name="Qwen 3.6 Plus",
        provider="openrouter",
        tier="best",
        is_free=True,
        context_window=1_000_000,
        description="Qwen 3.6 Plus — 1M context, high quality, free via OpenRouter.",
        supports_tools=False,
    ),
    ModelInfo(
        id="nvidia/nemotron-3-super-120b-a12b:free",
        name="Nemotron 3 Super 120B",
        provider="openrouter",
        tier="best",
        is_free=True,
        context_window=262_144,
        description="NVIDIA's 120B model — flagship quality, 262K context, free.",
        supports_tools=False,
    ),
    ModelInfo(
        id="nvidia/nemotron-3-nano-30b-a3b:free",
        name="Nemotron 3 Nano 30B",
        provider="openrouter",
        tier="fast",
        is_free=True,
        context_window=256_000,
        description="NVIDIA's 30B model — fast, 256K context, free via OpenRouter.",
        supports_tools=False,
    ),
    ModelInfo(
        id="stepfun/step-3.5-flash:free",
        name="Step 3.5 Flash",
        provider="openrouter",
        tier="fast",
        is_free=True,
        context_window=256_000,
        description="StepFun's flash model — fast inference, 256K context, free.",
        supports_tools=False,
    ),
    ModelInfo(
        id="arcee-ai/trinity-large-preview:free",
        name="Trinity Large Preview",
        provider="openrouter",
        tier="fast",
        is_free=True,
        context_window=131_000,
        description="Arcee AI Trinity — general purpose, 131K context, free.",
        supports_tools=False,
    ),

    # ── OpenRouter — Paid (optional, shown if OPENROUTER_API_KEY is set) ─
    ModelInfo(
        id="anthropic/claude-3.5-sonnet",
        name="Claude 3.5 Sonnet (via OR)",
        provider="openrouter",
        tier="best",
        is_free=False,
        context_window=200_000,
        description="Claude 3.5 Sonnet routed via OpenRouter.",
        supports_tools=True,
    ),
    ModelInfo(
        id="openai/gpt-4o",
        name="GPT-4o (via OR)",
        provider="openrouter",
        tier="best",
        is_free=False,
        context_window=128_000,
        description="GPT-4o routed via OpenRouter.",
        supports_tools=True,
    ),

    # ── Groq — Ultra-Fast Inference ───────────────────────────────────────
    # Free tier: 14,400 requests/day. Sign up at https://console.groq.com
    ModelInfo(
        id="llama-3.3-70b-versatile",
        name="Llama 3.3 70B (Groq)",
        provider="groq",
        tier="best",
        is_free=False,
        context_window=128_000,
        description="Llama 3.3 70B on Groq — best quality at blazing speed.",
        supports_tools=True,
    ),
    ModelInfo(
        id="llama-3.1-8b-instant",
        name="Llama 3.1 8B Instant (Groq)",
        provider="groq",
        tier="fast",
        is_free=False,
        context_window=128_000,
        description="World's fastest LLM inference. Near-instant responses.",
        supports_tools=True,
    ),
    ModelInfo(
        id="mixtral-8x7b-32768",
        name="Mixtral 8x7B (Groq)",
        provider="groq",
        tier="best",
        is_free=False,
        context_window=32_768,
        description="Mistral's MoE model — great at reasoning and coding.",
        supports_tools=True,
    ),
    ModelInfo(
        id="gemma2-9b-it",
        name="Gemma 2 9B (Groq)",
        provider="groq",
        tier="fast",
        is_free=False,
        context_window=8_192,
        description="Google's Gemma 2 9B at Groq speed.",
        supports_tools=False,
    ),

    # ── Google Gemini ─────────────────────────────────────────────────────
    # Free tier: 15 RPM, 1M TPM. Get key at https://aistudio.google.com
    ModelInfo(
        id="gemini-2.0-flash",
        name="Gemini 2.0 Flash",
        provider="gemini",
        tier="fast",
        is_free=False,
        context_window=1_000_000,
        description="Google's fastest model — 1M context, multimodal, tool support.",
        supports_tools=True,
    ),
    ModelInfo(
        id="gemini-2.0-flash-lite",
        name="Gemini 2.0 Flash Lite",
        provider="gemini",
        tier="fast",
        is_free=False,
        context_window=1_000_000,
        description="Cheapest Gemini model — great for high-volume tasks.",
        supports_tools=True,
    ),
    ModelInfo(
        id="gemini-1.5-pro",
        name="Gemini 1.5 Pro",
        provider="gemini",
        tier="best",
        is_free=False,
        context_window=2_000_000,
        description="2M context — ideal for long documents and deep analysis.",
        supports_tools=True,
    ),
    ModelInfo(
        id="gemini-1.5-flash",
        name="Gemini 1.5 Flash",
        provider="gemini",
        tier="fast",
        is_free=False,
        context_window=1_000_000,
        description="Fast and capable — the practical everyday Gemini model.",
        supports_tools=True,
    ),

    # ── Ollama — Local Models ─────────────────────────────────────────────
    # Shown only when OLLAMA_ENABLED=true. Model must be pulled first.
    ModelInfo(
        id="llama3.2",
        name="Llama 3.2 (local)",
        provider="ollama",
        tier="best",
        is_free=True,
        context_window=128_000,
        description="Meta's Llama 3.2 running locally via Ollama. Privacy first.",
        supports_tools=False,
    ),
    ModelInfo(
        id="llama3.1",
        name="Llama 3.1 (local)",
        provider="ollama",
        tier="best",
        is_free=True,
        context_window=128_000,
        description="Meta's Llama 3.1 running locally via Ollama.",
        supports_tools=False,
    ),
    ModelInfo(
        id="mistral",
        name="Mistral (local)",
        provider="ollama",
        tier="best",
        is_free=True,
        context_window=32_768,
        description="Mistral 7B running locally via Ollama.",
        supports_tools=False,
    ),
    ModelInfo(
        id="qwen2.5",
        name="Qwen 2.5 (local)",
        provider="ollama",
        tier="best",
        is_free=True,
        context_window=32_768,
        description="Alibaba Qwen 2.5 — great multilingual support, runs locally.",
        supports_tools=False,
    ),
    ModelInfo(
        id="phi3",
        name="Phi-3 (local)",
        provider="ollama",
        tier="fast",
        is_free=True,
        context_window=128_000,
        description="Microsoft Phi-3 — small, fast, 128K context. Runs locally.",
        supports_tools=False,
    ),
    ModelInfo(
        id="gemma2",
        name="Gemma 2 (local)",
        provider="ollama",
        tier="best",
        is_free=True,
        context_window=8_192,
        description="Google Gemma 2 running locally via Ollama.",
        supports_tools=False,
    ),
]

# ── Pricing (USD per million tokens) ────────────────────────────────────────
# (input_per_1m, output_per_1m) — used by chat_service to populate cost_usd
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o":                         (2.50,  10.00),
    "gpt-4o-mini":                    (0.15,   0.60),
    # Anthropic
    "claude-3-5-sonnet-20241022":     (3.00,  15.00),
    "claude-3-5-haiku-20241022":      (0.80,   4.00),
    # Groq
    "llama-3.3-70b-versatile":        (0.59,   0.79),
    "llama-3.1-70b-versatile":        (0.59,   0.79),
    "llama-3.1-8b-instant":           (0.05,   0.08),
    "mixtral-8x7b-32768":             (0.24,   0.24),
    "gemma2-9b-it":                   (0.20,   0.20),
    # Gemini
    "gemini-2.0-flash":               (0.075,  0.30),
    "gemini-2.0-flash-lite":          (0.075,  0.30),
    "gemini-1.5-pro":                 (1.25,   5.00),
    "gemini-1.5-flash":               (0.075,  0.30),
    # OpenRouter free models — $0
    "qwen/qwen3.6-plus:free":                       (0.0, 0.0),
    "nvidia/nemotron-3-super-120b-a12b:free":        (0.0, 0.0),
    "nvidia/nemotron-3-nano-30b-a3b:free":           (0.0, 0.0),
    "stepfun/step-3.5-flash:free":                   (0.0, 0.0),
    "arcee-ai/trinity-large-preview:free":           (0.0, 0.0),
    # Ollama — always free (local)
    "llama3.2":   (0.0, 0.0),
    "llama3.1":   (0.0, 0.0),
    "mistral":    (0.0, 0.0),
    "qwen2.5":    (0.0, 0.0),
    "phi3":       (0.0, 0.0),
    "gemma2":     (0.0, 0.0),
}


def compute_cost(model_id: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Return the USD cost for a generation given token counts and model pricing."""
    inp, out = MODEL_PRICING.get(model_id, (0.0, 0.0))
    return (prompt_tokens * inp + completion_tokens * out) / 1_000_000


# Quick lookup: model_id → ModelInfo
_MODEL_MAP: dict[str, ModelInfo] = {m.id: m for m in MODEL_REGISTRY}


def get_model_info(model_id: str) -> ModelInfo | None:
    """Look up a model by its id. Returns None if not in registry."""
    return _MODEL_MAP.get(model_id)


def provider_for_model(model_id: str) -> str:
    """
    Return the provider name for a given model id.
    Resolved purely from MODEL_REGISTRY + naming conventions — no global default needed.
    """
    info = _MODEL_MAP.get(model_id)
    if info:
        return info.provider
    # Unknown model — guess from naming conventions
    if model_id.startswith(("gpt-", "o1-", "o3-", "text-embedding")):
        return "openai"
    if model_id.startswith("claude-"):
        return "anthropic"
    if model_id.startswith("gemini-") or model_id.startswith("text-embedding-00"):
        return "gemini"
    if model_id.startswith(("llama-", "mixtral-", "gemma", "whisper-")):
        # Could be Groq (hosted) or Ollama (local) — prefer Groq if configured
        if settings.has_groq:
            return "groq"
        if settings.has_ollama:
            return "ollama"
    if "/" in model_id:
        return "openrouter"
    # Local model id (no slash) that isn't in registry → try Ollama if enabled
    if settings.has_ollama:
        return "ollama"
    # Last resort: whichever provider is configured
    if settings.has_openai:
        return "openai"
    if settings.has_anthropic:
        return "anthropic"
    if settings.has_groq:
        return "groq"
    if settings.has_gemini:
        return "gemini"
    if settings.has_openrouter:
        return "openrouter"
    raise ValueError(f"Cannot resolve provider for model {model_id!r} — no provider configured")


@lru_cache(maxsize=8)
def get_provider(provider_name: str) -> BaseAIProvider:
    """
    Cached provider instances — providers are stateless clients, safe to reuse.
    lru_cache ensures we don't recreate HTTP clients on every request.
    """
    if provider_name == "openai":
        from app.ai.providers.openai_provider import OpenAIProvider
        return OpenAIProvider()
    elif provider_name == "anthropic":
        from app.ai.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    elif provider_name == "ollama":
        from app.ai.providers.ollama_provider import OllamaProvider
        return OllamaProvider()
    elif provider_name == "openrouter":
        from app.ai.providers.openrouter_provider import OpenRouterProvider
        return OpenRouterProvider()
    elif provider_name == "groq":
        from app.ai.providers.groq_provider import GroqProvider
        return GroqProvider()
    elif provider_name == "gemini":
        from app.ai.providers.gemini_provider import GeminiProvider
        return GeminiProvider()
    else:
        raise ValueError(f"Unknown provider: {provider_name!r}")


def get_provider_for_model(model_id: str) -> tuple[BaseAIProvider, str]:
    """
    Given a model id, return (provider_instance, model_id).
    This is the primary entry point for chat_service.
    """
    provider_name = provider_for_model(model_id)
    return get_provider(provider_name), model_id


def get_provider_for_task(
    task: TaskType,
    preferred_model: str | None = None,
    preferred_provider: str | None = None,
) -> tuple[BaseAIProvider, str]:
    """
    Returns (provider_instance, model_name) for internal background tasks
    (title generation, summarization, embeddings).

    Resolution order:
    1. preferred_model set → auto-route via MODEL_REGISTRY
    2. preferred_provider set → use that provider's task-appropriate model
    3. Auto-pick first configured provider
    """
    if preferred_model:
        return get_provider_for_model(preferred_model)

    # Pick a provider: explicit > first configured
    if preferred_provider:
        provider_name = preferred_provider
    elif settings.has_openai:
        provider_name = "openai"
    elif settings.has_anthropic:
        provider_name = "anthropic"
    elif settings.has_groq:
        provider_name = "groq"
    elif settings.has_gemini:
        provider_name = "gemini"
    elif settings.has_openrouter:
        provider_name = "openrouter"
    elif settings.has_ollama:
        provider_name = "ollama"
    else:
        raise ValueError("No AI provider configured")

    provider = get_provider(provider_name)

    # Task → default model per provider
    if provider_name == "openai":
        model_map = {
            TaskType.CHAT: settings.DEFAULT_CHAT_MODEL,
            TaskType.FAST: settings.DEFAULT_FAST_MODEL,
            TaskType.REASONING: "o1-preview",
            TaskType.EMBEDDING: settings.DEFAULT_EMBED_MODEL,
            TaskType.SUMMARIZATION: settings.DEFAULT_FAST_MODEL,
        }
    elif provider_name == "anthropic":
        model_map = {
            TaskType.CHAT: settings.DEFAULT_ANTHROPIC_MODEL,
            TaskType.FAST: "claude-3-5-haiku-20241022",
            TaskType.REASONING: settings.DEFAULT_ANTHROPIC_MODEL,
            TaskType.EMBEDDING: settings.DEFAULT_EMBED_MODEL,
            TaskType.SUMMARIZATION: "claude-3-5-haiku-20241022",
        }
    elif provider_name == "ollama":
        model_map = {
            TaskType.CHAT: settings.OLLAMA_DEFAULT_MODEL,
            TaskType.FAST: settings.OLLAMA_DEFAULT_MODEL,
            TaskType.REASONING: settings.OLLAMA_DEFAULT_MODEL,
            TaskType.EMBEDDING: settings.OLLAMA_EMBED_MODEL,
            TaskType.SUMMARIZATION: settings.OLLAMA_DEFAULT_MODEL,
        }
    elif provider_name == "openrouter":
        model_map = {
            TaskType.CHAT: "qwen/qwen3.6-plus:free",
            TaskType.FAST: "nvidia/nemotron-3-nano-30b-a3b:free",
            TaskType.REASONING: "nvidia/nemotron-3-super-120b-a12b:free",
            # OpenRouter has no embeddings endpoint — caller should fall back to OpenAI
            TaskType.EMBEDDING: settings.DEFAULT_EMBED_MODEL,
            TaskType.SUMMARIZATION: "nvidia/nemotron-3-nano-30b-a3b:free",
        }
    elif provider_name == "groq":
        model_map = {
            TaskType.CHAT: settings.GROQ_DEFAULT_MODEL,
            TaskType.FAST: "llama-3.1-8b-instant",
            TaskType.REASONING: "llama-3.3-70b-versatile",
            # Groq has no embeddings — caller falls back to OpenAI/Ollama
            TaskType.EMBEDDING: settings.DEFAULT_EMBED_MODEL,
            TaskType.SUMMARIZATION: "llama-3.1-8b-instant",
        }
    elif provider_name == "gemini":
        model_map = {
            TaskType.CHAT: settings.GEMINI_DEFAULT_MODEL,
            TaskType.FAST: "gemini-2.0-flash-lite",
            TaskType.REASONING: "gemini-1.5-pro",
            TaskType.EMBEDDING: settings.GEMINI_EMBED_MODEL,
            TaskType.SUMMARIZATION: "gemini-2.0-flash-lite",
        }
    else:
        model_map = {t: settings.DEFAULT_CHAT_MODEL for t in TaskType}

    return provider, model_map[task]


def get_embedding_provider() -> tuple[BaseAIProvider, str]:
    """
    Returns the best available provider for generating embeddings.
    Priority: OpenAI > Gemini > Ollama > error.
    Groq and OpenRouter do not support embeddings, so we skip them.
    """
    if settings.has_openai:
        return get_provider("openai"), settings.DEFAULT_EMBED_MODEL
    if settings.has_gemini:
        return get_provider("gemini"), settings.GEMINI_EMBED_MODEL
    if settings.has_ollama:
        return get_provider("ollama"), settings.OLLAMA_EMBED_MODEL
    raise ValueError(
        "No embedding provider available. "
        "Set OPENAI_API_KEY, GEMINI_API_KEY, or OLLAMA_ENABLED=true."
    )
