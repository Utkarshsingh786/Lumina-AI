"""
Async SQLAlchemy engine and session factory.

Why async:
- FastAPI is async-first; blocking DB calls would negate the benefit
- asyncpg is the fastest PostgreSQL driver for Python
- SQLAlchemy 2.0 async works seamlessly with FastAPI's dependency injection

Connection pool sizing:
- pool_size=20: handles 20 concurrent queries per worker
- max_overflow=10: allows up to 10 additional connections under load
- Scale these with your worker count in production
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Create async engine with connection pooling
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_pre_ping=True,        # verify connection health before use
    echo=settings.APP_DEBUG,   # log SQL in development only
)

# Session factory — use this everywhere, never create sessions manually
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,    # prevent lazy-load after commit in async context
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session per request.
    Automatically commits on success, rolls back on exception.

    Usage:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
