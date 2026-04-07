"""Health check and app-info endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.utils.cache import get_redis

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health() -> dict:
    """Simple liveness check — returns 200 if app is running."""
    return {"status": "ok"}


@router.get("/detailed")
async def health_detailed(db: AsyncSession = Depends(get_db)) -> dict:
    """Detailed readiness check — verifies DB and Redis connectivity."""
    checks = {}

    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}


@router.get("/personas", tags=["personas"])
async def list_personas() -> dict:
    """
    Returns the available assistant personas with display metadata.
    No auth required — used by the frontend persona selector.
    """
    return {
        "personas": [
            {"id": "general",  "name": "General",  "description": "Helpful, accurate, and concise on any topic.", "icon": "✨"},
            {"id": "coding",   "name": "Coding",   "description": "Senior engineer mode: production-quality code and tradeoffs.", "icon": "💻"},
            {"id": "research", "name": "Research", "description": "Structured analysis with sourced facts and nuance.", "icon": "🔬"},
            {"id": "writing",  "name": "Writing",  "description": "Drafting, editing, and polishing written content.", "icon": "✍️"},
            {"id": "data",     "name": "Data",     "description": "Data analysis, SQL, Python/R, and visualizations.", "icon": "📊"},
            {"id": "support",  "name": "Support",  "description": "Empathetic, step-by-step problem solving.", "icon": "🤝"},
        ],
        "default": "general",
    }


@router.get("/models", tags=["models"])
async def list_models() -> dict:
    """
    Returns all available models grouped by provider.
    Derived from MODEL_REGISTRY — only includes providers that are configured.
    The frontend uses this to populate the model selector.
    """
    from app.ai.providers.router import MODEL_REGISTRY

    available: list[dict] = []

    for m in MODEL_REGISTRY:
        # Only include models whose provider is configured
        if m.provider == "openai" and not settings.has_openai:
            continue
        if m.provider == "anthropic" and not settings.has_anthropic:
            continue
        if m.provider == "ollama" and not settings.has_ollama:
            continue
        if m.provider == "openrouter" and not settings.has_openrouter:
            continue
        if m.provider == "groq" and not settings.has_groq:
            continue
        if m.provider == "gemini" and not settings.has_gemini:
            continue

        available.append({
            "id": m.id,
            "name": m.name,
            "provider": m.provider,
            "tier": m.tier,
            "is_free": m.is_free,
            "context_window": m.context_window,
            "description": m.description,
            "supports_tools": m.supports_tools,
        })

    # Determine the best default: prefer the configured default provider's best model
    default = settings.DEFAULT_CHAT_MODEL
    if available and not any(m["id"] == default for m in available):
        # Fallback to first available model
        default = available[0]["id"] if available else ""

    return {
        "models": available,
        "default": default,
        "providers": {
            "openai":      {"configured": settings.has_openai,      "label": "OpenAI"},
            "anthropic":   {"configured": settings.has_anthropic,   "label": "Anthropic"},
            "groq":        {"configured": settings.has_groq,        "label": "Groq"},
            "gemini":      {"configured": settings.has_gemini,      "label": "Google Gemini"},
            "ollama":      {"configured": settings.has_ollama,      "label": "Ollama (local)"},
            "openrouter":  {"configured": settings.has_openrouter,  "label": "OpenRouter"},
        },
    }
