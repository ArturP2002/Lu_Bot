"""Подключение к базе данных."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """Базовый класс моделей SQLAlchemy."""


_engine = None
_async_session_factory = None


def get_engine():
    """Ленивая инициализация движка БД."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Фабрика сессий."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _async_session_factory



async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Генератор сессии для FastAPI dependency."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
