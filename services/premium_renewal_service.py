"""Автопродление Premium списанием Искр с баланса."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import User
from services.app_settings_service import get_setting_int
from services.blogger_service import pay_blogger_commission
from services.sparks_service import add_transaction

logger = logging.getLogger(__name__)

# Не трогаем «навсегда» (рефералка / админ)
FOREVER_YEAR = 2090
RENEW_DAYS = 30
# Окно: истекает в ближайший час или истекло не более суток назад
LOOKAHEAD = timedelta(hours=1)
GRACE = timedelta(days=1)


def _is_forever(until: datetime | None) -> bool:
    if not until:
        return False
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    return until.year >= FOREVER_YEAR


async def renew_expired_premium(session: AsyncSession) -> list[tuple[User, int, datetime]]:
    """
    Продлить Premium на 1 месяц пользователям с достаточным балансом.
    Возвращает список (user, price, new_until) успешно продлённых.
    """
    now = datetime.now(timezone.utc)
    price = await get_setting_int(session, "premium_price_1m")
    if price <= 0:
        return []

    window_start = now - GRACE
    window_end = now + LOOKAHEAD

    result = await session.execute(
        select(User).where(
            and_(
                User.premium_until.is_not(None),
                User.premium_until >= window_start,
                User.premium_until <= window_end,
                User.is_banned.is_(False),
                User.sparks_balance >= price,
            )
        )
    )
    users = list(result.scalars().all())
    renewed: list[tuple[User, int, datetime]] = []

    for user in users:
        if _is_forever(user.premium_until):
            continue
        until = user.premium_until
        if until is None:
            continue
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)

        if user.sparks_balance < price:
            continue

        try:
            await add_transaction(session, user.id, -price, "premium_auto_renew")
            await pay_blogger_commission(session, user, price, purpose="premium")
            base = until if until > now else now
            user.premium_until = base + timedelta(days=RENEW_DAYS)
            renewed.append((user, price, user.premium_until))
            logger.info(
                "Premium auto-renewed user_id=%s price=%s until=%s",
                user.id,
                price,
                user.premium_until,
            )
        except Exception:
            logger.exception("Premium auto-renew failed user_id=%s", user.id)

    return renewed
