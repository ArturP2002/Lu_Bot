"""Выплата Искр через Telegram Stars (подарки с баланса бота)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)


@dataclass
class StarsPayoutResult:
    ok: bool
    stars_spent: int = 0
    gifts_sent: int = 0
    error: str | None = None


async def get_bot_star_balance(bot: Bot) -> int:
    """Текущий баланс Stars бота."""
    try:
        balance = await bot.get_my_star_balance()
        # StarAmount: amount field
        return int(getattr(balance, "amount", 0) or 0)
    except Exception as e:
        logger.warning("get_my_star_balance failed: %s", e)
        return 0


def _gift_denominations(gifts: list) -> list[int]:
    return sorted({int(g.star_count) for g in gifts if getattr(g, "star_count", 0) and g.star_count > 0})


def _pick_gifts(gifts: list, target: int) -> list:
    """Подобрать подарки на сумму target (жадно от дорогих к дешёвым, затем добор).

    Важно: Telegram позволяет отправлять только готовые gift-пакеты с фиксированной
    ценой в Stars (например 15/25/50…). Произвольную сумму вроде 10⭐ набрать
    нельзя, если нет комбинации номиналов, дающей ровно target.
    """
    available = sorted(
        [g for g in gifts if getattr(g, "star_count", 0) and g.star_count > 0],
        key=lambda g: g.star_count,
        reverse=True,
    )
    if not available:
        return []
    cheapest = min(available, key=lambda g: g.star_count)
    if cheapest.star_count > target:
        return []

    picked: list = []
    remaining = target
    # Сначала крупные
    for g in available:
        while remaining >= g.star_count and remaining > 0:
            # не уходим в минус дальше цели
            if remaining - g.star_count < 0:
                break
            picked.append(g)
            remaining -= g.star_count
            if len(picked) > 50:  # safety
                break
        if remaining == 0 or len(picked) > 50:
            break

    # Добор самым дешёвым, если остаток покрывается
    while 0 < remaining and cheapest.star_count <= remaining and len(picked) <= 50:
        picked.append(cheapest)
        remaining -= cheapest.star_count

    if remaining != 0:
        # Не удалось набрать ровно — частичная выплата недопустима
        return []
    return picked


async def payout_stars_via_gifts(
    bot: Bot,
    telegram_user_id: int,
    stars_amount: int,
    *,
    note: str = "LUMA payout",
) -> StarsPayoutResult:
    """
    Реальная выплата Stars пользователю через sendGift с баланса бота.
    1 Искра = 1 Star (net_amount заявки).
    """
    if stars_amount <= 0:
        return StarsPayoutResult(ok=False, error="Сумма должна быть > 0")

    balance = await get_bot_star_balance(bot)
    if balance < stars_amount:
        return StarsPayoutResult(
            ok=False,
            error=f"Недостаточно Stars на балансе бота ({balance} < {stars_amount})",
        )

    try:
        gifts_resp = await bot.get_available_gifts()
        gifts = list(getattr(gifts_resp, "gifts", None) or [])
    except Exception as e:
        logger.exception("get_available_gifts failed")
        return StarsPayoutResult(ok=False, error=f"Не удалось получить список подарков: {e}")

    picked = _pick_gifts(gifts, stars_amount)
    if not picked:
        denoms = _gift_denominations(gifts)
        denoms_txt = ", ".join(str(d) for d in denoms[:20]) if denoms else "список пуст"
        return StarsPayoutResult(
            ok=False,
            error=(
                f"Не удалось подобрать подарки ровно на {stars_amount}⭐. "
                f"Доступные номиналы gift: {denoms_txt}. "
                "Выплатите вручную или выведите сумму, которую можно собрать из этих номиналов."
            ),
        )
    spent = 0
    sent = 0
    try:
        for i, gift in enumerate(picked):
            text = note if i == 0 else None
            await bot.send_gift(
                gift_id=gift.id,
                user_id=telegram_user_id,
                text=text,
            )
            spent += int(gift.star_count)
            sent += 1
    except TelegramAPIError as e:
        logger.exception("send_gift failed after %s gifts", sent)
        return StarsPayoutResult(
            ok=False,
            stars_spent=spent,
            gifts_sent=sent,
            error=f"Ошибка sendGift после {sent} подарков: {e}",
        )

    return StarsPayoutResult(ok=True, stars_spent=spent, gifts_sent=sent)
