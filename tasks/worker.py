"""Фоновые задачи."""

import asyncio
import json
import logging

from arq import cron
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


async def renew_premium_subscriptions(ctx) -> None:
    """Раз в час: автопродление Premium списанием Искр (1 месяц)."""
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from zoneinfo import ZoneInfo

    from services.premium_renewal_service import renew_expired_premium

    factory = get_session_factory()
    async with factory() as session:
        renewed = await renew_expired_premium(session)
        await session.commit()

    if not renewed or not settings.bot_token:
        return

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        for user, price, until in renewed:
            until_local = until.astimezone(ZoneInfo("Europe/Moscow"))
            until_str = until_local.strftime("%d.%m.%Y %H:%M")
            try:
                await bot.send_message(
                    user.telegram_id,
                    f"Premium продлён автоматически на 1 месяц (−{price} искр✨).\n"
                    f"Действует до: <b>{until_str}</b> (МСК)",
                )
            except Exception as e:
                logger.warning("Не удалось уведомить о продлении %s: %s", user.telegram_id, e)
            await asyncio.sleep(0.05)
    finally:
        await bot.session.close()


async def backfill_user_event_geo(ctx) -> dict:
    """Фоновый backfill координат (запускать вручную через enqueue)."""
    from services.geo_backfill import backfill_user_event_geo as _run

    return await _run(ctx)


async def regeocode_entity(ctx, entity_type: str, entity_id: int) -> bool:
    from services.geo_backfill import regeocode_entity as _run

    return await _run(ctx, entity_type, entity_id)


async def reset_exhausted_feeds(ctx) -> int:
    """Ночной сброс скипов для пользователей, исчерпавших ленту (00:05 МСК = 21:05 UTC)."""
    factory = get_session_factory()
    async with factory() as session:
        from services.feed_service import reset_exhausted_feed_skips

        count = await reset_exhausted_feed_skips(session)
        await session.commit()
    logger.info("reset_exhausted_feeds: cleared skips for %s users", count)
    return count


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [
        send_broadcast,
        renew_premium_subscriptions,
        backfill_user_event_geo,
        regeocode_entity,
        reset_exhausted_feeds,
    ]
    cron_jobs = [
        cron(renew_premium_subscriptions, minute={15}, unique=True),
        # 00:05 Europe/Moscow == 21:05 UTC (MSK = UTC+3, без DST)
        cron(reset_exhausted_feeds, hour={21}, minute={5}, unique=True),
    ]
