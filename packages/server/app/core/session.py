from collections.abc import Generator
from typing import Any
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, async_sessionmaker, create_async_engine
from .config import config

try:
    from ..models.base import Base
except ImportError:  # pragma: no cover - fallback for direct script execution
    from models.base import Base

DATABASE_URL = config.DATABASE_URL

if DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("sqlite:///") and not DATABASE_URL.startswith("sqlite+aiosqlite:///"):
    DATABASE_URL = DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")

engine: AsyncEngine = create_async_engine(DATABASE_URL, echo=config.SQLALCHEMY_ECHO)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for request-scoped use."""
    async with AsyncSessionLocal() as db:
        yield db


__all__ = ["Base", "AsyncSessionLocal", "get_db"]
