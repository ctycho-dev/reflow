# tests/integration/conftest.py
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool
from app.main import app
from app.database.connection import Base

# point at a dedicated Reflow test database — adjust host/port/creds to match
# your local test DB (mirror the analyser app's separate test DB convention)
TEST_DATABASE_URL = "postgresql+asyncpg://test_user:test_pass@localhost:5433/test_reflow_db"


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_engine():
    """Create the test database schema once per session, drop it at the end."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="session")
def session_factory(test_engine):
    return async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest_asyncio.fixture(loop_scope="function")
async def db_session(session_factory) -> AsyncGenerator[AsyncSession, None]:
    """
    Per-test session. Rolls back at the end so tests don't leak state into each
    other (each test sees a clean slate without a full schema rebuild).
    """
    async with session_factory() as session:
        yield session
        await session.rollback()
