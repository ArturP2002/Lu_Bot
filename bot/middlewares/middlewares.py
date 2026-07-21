"""Middleware бота."""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session_factory
from services.user_service import get_or_create_user


class DatabaseMiddleware(BaseMiddleware):
    """Проброс сессии БД в handlers."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        factory = get_session_factory()
        async with factory() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise


class UserMiddleware(BaseMiddleware):
    """Загрузка пользователя."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session: AsyncSession = data["session"]
        user = None
        from_user = data.get("event_from_user")
        if from_user is None and hasattr(event, "from_user") and event.from_user:
            from_user = event.from_user

        if from_user:
            user = await get_or_create_user(session, from_user.id, from_user.username)
        data["user"] = user
        data["tg_user"] = from_user
        return await handler(event, data)


class RedisMiddleware(BaseMiddleware):
    """Проброс Redis."""

    def __init__(self, redis: Redis):
        self.redis = redis

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        data["redis"] = self.redis
        return await handler(event, data)


class ThrottleMiddleware(BaseMiddleware):
    """Простой rate limit."""

    def __init__(self, redis: Redis, rate: float = 0.5):
        self.redis = redis
        self.rate = rate

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        from aiogram.types import CallbackQuery, Message

        from bot.texts.ui_labels import all_main_menu_texts

        from_user = data.get("tg_user")
        if from_user:
            skip = False
            if isinstance(event, CallbackQuery):
                skip = True
            elif isinstance(event, Message):
                text = (event.text or "").strip()
                if text.startswith("/"):
                    skip = True
                elif text in all_main_menu_texts():
                    skip = True

            if not skip:
                key = f"throttle:{from_user.id}"
                if await self.redis.exists(key):
                    return None
                await self.redis.set(key, "1", px=max(1, int(self.rate * 1000)))
        return await handler(event, data)
