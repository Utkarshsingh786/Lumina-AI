"""
Application configuration using Pydantic Settings v2.

Provider selection is fully model-driven: pick a model in the UI and the
correct provider is resolved automatically from MODEL_REGISTRY. There is
no DEFAULT_AI_PROVIDER flag — the model ID is the single source of truth.

DEFAULT_CHAT_MODEL is only used as a fallback when an API client does not
send a model field (CLI, scripts, etc.). The frontend always sends one.
"""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────
    APP_NAME: str = "Lumina AI"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_DEBUG: bool = False
    APP_SECRET_KEY: str
    APP_VERSION: str = "0.1.0"

    # ── Server ────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1

    # ── Database ──────────────────────────────────────
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30

    # ── Redis ─────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600

    # ── Auth ──────────────────────────────────────────
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ALGORITHM: str = "HS256"

    # ── CORS ──────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    # ── AI Providers ──────────────────────────────────
    # Provider is resolved automatically from the model id (see router.py).
    # You do NOT configure a default provider — you configure a default model.
    # The model's entry in MODEL_REGISTRY declares which provider handles it.

    # OpenAI — https://platform.openai.com
    OPENAI_API_KEY: str = ""
    OPENAI_ORG_ID: str = ""
    DEFAULT_CHAT_MODEL: str = "gpt-4o"       # fallback for API clients without a model field
    DEFAULT_FAST_MODEL: str = "gpt-4o-mini"  # used for title gen, summaries
    DEFAULT_EMBED_MODEL: str = "text-embedding-3-small"

    # Anthropic — https://console.anthropic.com
    ANTHROPIC_API_KEY: str = ""
    DEFAULT_ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"

    # OpenRouter — free-tier models available, no credit card required
    # Sign up: https://openrouter.ai | Free models end in :free
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Groq — ultra-fast inference (free tier available)
    # Sign up: https://console.groq.com | Free: 14,400 req/day on llama3.1-8b
    GROQ_API_KEY: str = ""
    GROQ_DEFAULT_MODEL: str = "llama-3.1-8b-instant"

    # Google Gemini — free tier: 15 RPM, 1M TPM on Flash
    # Get key: https://aistudio.google.com/app/apikey
    GEMINI_API_KEY: str = ""
    GEMINI_DEFAULT_MODEL: str = "gemini-2.0-flash"
    GEMINI_EMBED_MODEL: str = "text-embedding-004"

    # Ollama — 100% free local inference
    # Install: https://ollama.com | ollama pull llama3.2
    OLLAMA_ENABLED: bool = False
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_DEFAULT_MODEL: str = "llama3.2"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"

    # ── Voice (STT / TTS) ─────────────────────────────
    # Requires OPENAI_API_KEY. Whisper for STT, OpenAI TTS for synthesis.
    VOICE_STT_MODEL: str = "whisper-1"
    VOICE_TTS_MODEL: str = "tts-1"       # tts-1 (fast) or tts-1-hd (higher quality)
    VOICE_TTS_VOICE: str = "alloy"       # alloy | echo | fable | onyx | nova | shimmer

    # ── AI Behavior ───────────────────────────────────
    MAX_CONTEXT_TOKENS: int = 128_000
    CONTEXT_RESERVE_TOKENS: int = 2_000
    SUMMARY_TRIGGER_MESSAGES: int = 30
    MEMORY_EXTRACTION_ENABLED: bool = True

    # ── Tools ─────────────────────────────────────────
    TOOLS_ENABLED: bool = True
    TOOLS_MAX_ROUNDS: int = 5

    # ── Rate Limiting ─────────────────────────────────
    RATE_LIMIT_CHAT_PER_MINUTE: int = 30
    RATE_LIMIT_API_PER_MINUTE: int = 100

    # ── File Uploads ──────────────────────────────────
    MAX_FILE_SIZE_MB: int = 25
    ALLOWED_FILE_TYPES: list[str] = [
        "application/pdf",
        "text/plain",
        "text/markdown",
        "image/png",
        "image/jpeg",
    ]
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    LOCAL_STORAGE_PATH: str = "./uploads"

    # ── Celery ────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Logging ───────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "pretty"] = "json"

    # ── Computed helpers ─────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def has_openai(self) -> bool:
        return bool(self.OPENAI_API_KEY)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.ANTHROPIC_API_KEY)

    @property
    def has_ollama(self) -> bool:
        return self.OLLAMA_ENABLED

    @property
    def has_openrouter(self) -> bool:
        return bool(self.OPENROUTER_API_KEY)

    @property
    def has_groq(self) -> bool:
        return bool(self.GROQ_API_KEY)

    @property
    def has_gemini(self) -> bool:
        return bool(self.GEMINI_API_KEY)

    @field_validator("APP_SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("APP_SECRET_KEY must be at least 32 characters")
        return v

    @model_validator(mode="after")
    def validate_providers(self) -> "Settings":
        """At least one provider must be configured or the app can't do anything."""
        has_any = (
            self.OPENAI_API_KEY
            or self.ANTHROPIC_API_KEY
            or self.OLLAMA_ENABLED
            or self.OPENROUTER_API_KEY
            or self.GROQ_API_KEY
            or self.GEMINI_API_KEY
        )
        if not has_any:
            raise ValueError(
                "No AI provider configured. Set at least one of: "
                "OPENAI_API_KEY, ANTHROPIC_API_KEY, OPENROUTER_API_KEY, "
                "GROQ_API_KEY, GEMINI_API_KEY, or OLLAMA_ENABLED=true in backend/.env"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
