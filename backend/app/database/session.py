"""Database session management with async SQLAlchemy."""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from typing import AsyncGenerator
from backend.app.core.config import settings

engine_kwargs = {
    "echo": settings.DEBUG,
}
if not str(settings.DATABASE_URL).startswith("sqlite"):
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
    })
else:
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables (for development/testing only)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database engine."""
    await engine.dispose()
