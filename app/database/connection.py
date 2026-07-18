# app/database/connection.py
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base

from app.core.logger import get_logger
from app.core.sections import PostgresConfig  # adjust path to your config module

logger = get_logger()

Base = declarative_base()


class DatabaseManager:
    def __init__(self, config: PostgresConfig):
        self.config = config
        self.engine: AsyncEngine | None = None
        self.async_session: async_sessionmaker | None = None

    def init_engine(self, *, application_name: str = "reflow"):
        self.engine = create_async_engine(
            self.config.url,
            echo=False,
            pool_size=self.config.pool_size,
            max_overflow=self.config.max_overflow,
            pool_pre_ping=self.config.pool_pre_ping,
            connect_args={"server_settings": {"application_name": application_name}},
        )
        self.async_session = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

    async def create_all_tables(self):
        if not self.engine:
            raise RuntimeError("Engine not initialized. Call init_engine() first.")
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def session_scope(self):
        if not self.async_session:
            raise RuntimeError("Session not initialized. Call init_engine() first.")
        session = self.async_session()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def close(self):
        if self.engine:
            await self.engine.dispose()
