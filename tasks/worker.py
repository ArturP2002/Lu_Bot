"""Фоновые задачи."""

import asyncio
import json
import logging

from arq.connections import RedisSettings
from sqlalchemy import select

from config import get_settings
from core.database import get_session_factory
from models import Broadcast, User
from services.user_service import is_premium

logger = logging.getLogger(__name__)
settings = get_settings()


def _apply_broadcast_filters(users: list[User], filters: dict | None) -> list[User]:
    if not filters:
        return users
    gender = filters.get("gender")
    premium = filters.get("premium")
    out = users
    if gender and gender != "all":
        out = [u for u in out if u.gender == gender]
    if premium == "premium":
        out = [u for u in out if is_premium(u)]
    elif premium == "free":
        out = [u for u in out if not is_premium(u)]
    return out


async def send_broadcast(ctx, broadcast_id: int) -> None:
    """Отправка массовой рассылки."""
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    factory = get_session_factory()
    async with factory() as session:
        bc = await session.get(Broadcast, broadcast_id)
        if not bc:
            return
        if bc.status not in ("pending", "failed"):
            return
        bc.status = "running"
        await session.commit()

        filters = None
        if bc.filters_json:
            try:
                filters = json.loads(bc.filters_json)
            except json.JSONDecodeError:
                filters = None

        if bc.target_user_ids:
            ids = json.loads(bc.target_user_ids)
            result = await session.execute(select(User).where(User.id.in_(ids)))
            users = list(result.scalars().all())
        else:
            result = await session.execute(select(User).where(User.is_banned.is_(False)))
            users = _apply_broadcast_filters(list(result.scalars().all()), filters)

        bc.total_count = len(users)
        sent = 0
        for u in users:
            try:
                await bot.send_message(u.telegram_id, bc.message_text)
                sent += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.warning("Ошибка отправки %s: %s", u.telegram_id, e)
        bc.sent_count = sent
        bc.status = "completed"
        await session.commit()
    await bot.session.close()


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [send_broadcast]
