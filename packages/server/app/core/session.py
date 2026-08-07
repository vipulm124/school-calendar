from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, async_sessionmaker, create_async_engine
from .config import config

try:
    from ..models.base import Base
except ImportError:  # pragma: no cover - fallback for direct script execution
    from models.base import Base


def _to_async_database_url(url: str) -> str:
    """Ensure SQLAlchemy async drivers are used for Postgres and SQLite."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]

    if url.startswith("sqlite+aiosqlite://"):
        return url
    if url.startswith("sqlite://"):
        return "sqlite+aiosqlite://" + url[len("sqlite://") :]

    return url


DATABASE_URL = _to_async_database_url(config.DATABASE_URL)

engine: AsyncEngine = create_async_engine(DATABASE_URL, echo=config.SQLALCHEMY_ECHO)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for request-scoped use."""
    async with AsyncSessionLocal() as db:
        yield db


__all__ = ["Base", "AsyncSessionLocal", "get_db"]
