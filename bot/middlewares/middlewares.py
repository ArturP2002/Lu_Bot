"""Middleware бота."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery, TelegramObject, Update
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session_factory
from services.user_service import get_or_create_user

logger = logging.getLogger(__name__)


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


def _unwrap_event(event: TelegramObject) -> TelegramObject:
    """Throttle висит на dp.update — event это Update, нужен внутренний объект."""
    if isinstance(event, Update):
        return event.event
    return event


def _message_from_event(event: TelegramObject) -> Message | None:
    if isinstance(event, Message):
        return event
    if isinstance(event, Update):
        return event.message
    return None


def _is_media_message(obj: TelegramObject) -> bool:
    return isinstance(obj, Message) and bool(
        obj.media_group_id or obj.photo or obj.video or obj.video_note or obj.animation
    )


class AlbumMiddleware(BaseMiddleware):
    """Собрать медиагруппу и вызвать цепочку один раз с data['album'].

    Каждый файл альбома — отдельный Update. Без буфера хендлер успевает
    сохранить только первое вложение.
    """

    def __init__(self, latency: float = 1.0):
        self.latency = latency
        self._albums: dict[str, list[Message]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        message = _message_from_event(event)
        if message is None or not message.media_group_id:
            return await handler(event, data)

        key = f"{message.chat.id}:{message.media_group_id}"
        lock = self._lock_for(key)
        async with lock:
            album = self._albums.setdefault(key, [])
            album.append(message)
            count = len(album)

        await asyncio.sleep(self.latency)

        async with lock:
            album = self._albums.get(key)
            if album is None or len(album) != count:
                return None
            self._albums.pop(key, None)
            self._locks.pop(key, None)
            messages = list(album)

        messages.sort(key=lambda item: item.message_id)
        data["album"] = messages
        logger.info("album %s assembled: %s items", message.media_group_id, len(messages))
        return await handler(event, data)


class ThrottleMiddleware(BaseMiddleware):
    """Простой rate limit (не трогает платежи, меню и медиа)."""

    def __init__(self, redis: Redis, rate: float = 0.5):
        self.redis = redis
        self.rate = rate

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        from bot.texts.ui_labels import all_main_menu_texts

        obj = _unwrap_event(event)

        # Платежный поток нельзя дропать: pre_checkout → successful_payment идут подряд
        if isinstance(obj, PreCheckoutQuery):
            return await handler(event, data)
        if isinstance(obj, Message) and obj.successful_payment:
            return await handler(event, data)
        if isinstance(obj, CallbackQuery):
            return await handler(event, data)
        if _is_media_message(obj):
            return await handler(event, data)

        from_user = data.get("tg_user")
        if from_user and isinstance(obj, Message):
            text = (obj.text or "").strip()
            if not (text.startswith("/") or text in all_main_menu_texts()):
                key = f"throttle:{from_user.id}"
                if await self.redis.exists(key):
                    return None
                await self.redis.set(key, "1", px=max(1, int(self.rate * 1000)))
        return await handler(event, data)
