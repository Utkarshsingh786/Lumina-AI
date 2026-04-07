"""
FastAPI application factory.

Startup order:
1. Logging configured
2. FastAPI app created with metadata
3. Middleware stack applied (order matters!)
4. Exception handlers registered
5. Routers mounted
6. Lifespan events: DB init, Redis connect, cleanup on shutdown
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import admin, agents, auth, conversations, documents, health, memory, organizations, share, stream, usage, voice
from app.core.config import settings
from app.core.exceptions import LuminaError
from app.core.logging import get_logger, setup_logging
from app.core.middleware import LoggingMiddleware, RequestIDMiddleware

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown hooks."""
    logger.info("app.startup", version=settings.APP_VERSION, env=settings.APP_ENV)

    # Verify DB connectivity at startup
    try:
        from app.db.session import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("app.db_connected")
    except Exception as e:
        logger.error("app.db_connection_failed", error=str(e))

    # Warm Redis connection
    try:
        from app.utils.cache import get_redis
        redis = await get_redis()
        await redis.ping()
        logger.info("app.redis_connected")
    except Exception as e:
        logger.warning("app.redis_connection_failed", error=str(e))

    yield  # App is running

    # Shutdown
    logger.info("app.shutdown")
    from app.db.session import engine
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Production-grade AI Chatbot Platform API",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── Middleware (outermost to innermost) ───────────
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # ── Exception Handlers ────────────────────────────
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """
        Normalize FastAPI/Pydantic 422 errors to the same {error_code, message, details}
        shape as our custom exceptions, so the frontend has one consistent format.
        """
        errors = exc.errors()
        # Build a human-readable message from the first error
        first = errors[0] if errors else {}
        # loc is like ["body", "email"] — skip the "body" prefix
        loc_parts = [str(p) for p in first.get("loc", []) if p != "body"]
        field = ".".join(loc_parts)
        raw_msg = first.get("msg", "Invalid request data")
        message = f"{field}: {raw_msg}" if field else raw_msg
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error_code": "VALIDATION_ERROR",
                "message": message,
                "details": {"errors": errors},
            },
        )

    @app.exception_handler(LuminaError)
    async def lumina_exception_handler(
        request: Request, exc: LuminaError
    ) -> JSONResponse:
        """
        All our custom exceptions produce clean, structured JSON errors.
        Never leak stack traces to the client.
        """
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all for unhandled exceptions — log fully, return minimal info."""
        logger.exception("app.unhandled_exception", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {},
            },
        )

    # ── Routers ───────────────────────────────────────
    API_PREFIX = "/api/v1"
    app.include_router(health.router,        prefix=API_PREFIX)
    app.include_router(auth.router,          prefix=API_PREFIX)
    app.include_router(conversations.router, prefix=API_PREFIX)
    app.include_router(stream.router,        prefix=API_PREFIX)
    app.include_router(memory.router,        prefix=API_PREFIX)
    app.include_router(documents.router,     prefix=API_PREFIX)
    # Phase 3
    app.include_router(share.router,         prefix=API_PREFIX)
    app.include_router(usage.router,         prefix=API_PREFIX)
    app.include_router(voice.router,         prefix=API_PREFIX)
    app.include_router(admin.router,         prefix=API_PREFIX)
    app.include_router(agents.router,        prefix=API_PREFIX)
    app.include_router(organizations.router, prefix=API_PREFIX)

    return app


app = create_app()
