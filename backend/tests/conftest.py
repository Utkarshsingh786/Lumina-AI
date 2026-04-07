"""
Test configuration and fixtures.

Design: use a test PostgreSQL database (not mocks) for integration tests.
Why: real DB tests catch SQL syntax errors, index issues, and migration problems
that mocks would silently pass. This matches the "don't mock the DB" principle.

For unit tests (pure functions, no DB): use standard pytest with mocks.
For integration tests: use the async session fixture with rollback after each test.
"""

import asyncio
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from httpx import AsyncClient, ASGITransport

from app.core.config import settings
from app.db.base import Base
from app.main import app

# Use a separate test database
TEST_DATABASE_URL = settings.DATABASE_URL.replace("/lumina_db", "/lumina_test")


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the session scope."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test tables once per test session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db(test_engine) -> AsyncSession:
    """
    Provides a database session that rolls back after each test.
    This ensures test isolation without re-creating the schema.
    """
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def client(db) -> AsyncClient:
    """HTTP client for API integration tests."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def sample_user_data():
    return {
        "email": "test@example.com",
        "username": "testuser",
        "password": "TestPass123",
        "full_name": "Test User",
    }
