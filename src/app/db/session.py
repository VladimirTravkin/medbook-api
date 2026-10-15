"""Async database engine, session factory and dependency."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _create_engine(*, echo: bool) -> AsyncEngine:
    """Create an async engine with standard settings."""
    return create_async_engine(
        settings.database_url,
        echo=echo,
        future=True,
        pool_pre_ping=True,
    )


engine = _create_engine(echo=settings.APP_DEBUG)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


def create_quiet_session_maker() -> async_sessionmaker[AsyncSession]:
    """Create a session maker with SQL logging disabled.

    Intended for CLI scripts (migrations, seeders, admin tools) where
    SQL echo output is noise and may leak sensitive data into logs.
    """
    quiet_engine = _create_engine(echo=False)
    return async_sessionmaker(
        quiet_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
