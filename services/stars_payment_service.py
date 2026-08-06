"""Telegram Stars: запись платежей и синхронизация истории в админку."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.types import TransactionPartnerUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Payment, User
from models.entities import PaymentProvider, PaymentStatus
from services.sparks_service import add_transaction

logger = logging.getLogger(__name__)


def parse_buy_sparks_amount(payload: str | None, stars_amount: int) -> int:
    """Сколько искр купили: из payload buy_sparks:N, иначе сумма Stars."""
    payload = payload or ""
    if payload.startswith("buy_sparks:"):
        try:
            return int(payload.split(":", 1)[1])
        except ValueError:
            pass
    return max(1, int(stars_amount))


async def get_payment_by_external_id(session: AsyncSession, external_id: str | None) -> Payment | None:
    if not external_id:
        return None
    result = await session.execute(select(Payment).where(Payment.external_id == external_id))
    return result.scalar_one_or_none()


async def _find_near_duplicate(
    session: AsyncSession,
    *,
    user_id: int,
    amount_sparks: int,
    paid_at: datetime,
) -> Payment | None:
    """Уже есть stars-платёж того же пользователя на ту же сумму около того же времени."""
    window = timedelta(minutes=5)
    result = await session.execute(
        select(Payment).where(
            Payment.user_id == user_id,
            Payment.provider == PaymentProvider.STARS.value,
            Payment.amount_sparks == amount_sparks,
            Payment.status == PaymentStatus.SUCCEEDED.value,
        )
    )
    for p in result.scalars().all():
        ts = p.paid_at or p.created_at
        if ts is None:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if abs(ts - paid_at) <= window:
            return p
    return None


async def record_stars_payment(
    session: AsyncSession,
    user: User,
    *,
    external_id: str,
    amount_sparks: int,
    amount_stars: int,
    paid_at: datetime | None = None,
    credit_balance: bool = True,
) -> Payment:
    """Создать/обновить succeeded Stars-платёж. Идемпотентно по external_id.

    amount_stars (XTR) пишем в amount_rub — отдельной колонки нет; в админке для stars это Stars.
    """
    paid_at = paid_at or datetime.now(timezone.utc)
    stars_paid = float(max(1, int(amount_stars)))
    existing = await get_payment_by_external_id(session, external_id)
    if existing:
        if existing.status != PaymentStatus.SUCCEEDED.value:
            existing.status = PaymentStatus.SUCCEEDED.value
            existing.paid_at = paid_at
            existing.amount_sparks = amount_sparks
        if not existing.amount_rub:
            existing.amount_rub = stars_paid
        return existing

    near = await _find_near_duplicate(
        session, user_id=user.id, amount_sparks=amount_sparks, paid_at=paid_at
    )
    if near:
        if not near.external_id:
            near.external_id = external_id
        if not near.amount_rub:
            near.amount_rub = stars_paid
        return near

    payment = Payment(
        user_id=user.id,
        provider=PaymentProvider.STARS.value,
        external_id=external_id,
        amount_sparks=amount_sparks,
        amount_rub=stars_paid,
        status=PaymentStatus.SUCCEEDED.value,
        purpose="buy_sparks",
        paid_at=paid_at,
    )
    session.add(payment)
    await session.flush()

    if credit_balance:
        await add_transaction(session, user.id, amount_sparks, "purchase", payment.id)
        from services.blogger_service import pay_blogger_commission

        await pay_blogger_commission(session, user, amount_sparks, purpose="buy_sparks_stars")
    return payment


async def sync_star_transactions_to_payments(
    session: AsyncSession,
    bot: Bot,
    *,
    limit: int = 100,
) -> int:
    """Подтянуть входящие Stars-покупки из Telegram в таблицу payments (без повторного зачисления)."""
    created = 0
    updated = 0
    try:
        result = await bot.get_star_transactions(offset=0, limit=limit)
    except Exception as e:
        logger.warning("get_star_transactions failed: %s", e)
        return 0

    for tx in result.transactions or []:
        source = tx.source
        if not isinstance(source, TransactionPartnerUser):
            continue

        payload = source.invoice_payload or ""
        if not payload.startswith("buy_sparks:"):
            continue

        tg_user = source.user
        if not tg_user:
            continue

        external_id = str(tx.id)
        stars_paid = float(max(1, int(tx.amount)))
        amount_sparks = parse_buy_sparks_amount(payload, tx.amount)
        paid_at = datetime.fromtimestamp(tx.date, tz=timezone.utc) if tx.date else datetime.now(timezone.utc)

        existing = await get_payment_by_external_id(session, external_id)
        if existing:
            if not existing.amount_rub:
                existing.amount_rub = stars_paid
                updated += 1
            continue

        user_row = await session.execute(select(User).where(User.telegram_id == tg_user.id))
        user = user_row.scalar_one_or_none()
        if not user:
            continue

        near = await _find_near_duplicate(
            session, user_id=user.id, amount_sparks=amount_sparks, paid_at=paid_at
        )
        if near:
            if not near.amount_rub:
                near.amount_rub = stars_paid
                updated += 1
            if not near.external_id:
                near.external_id = external_id
            continue

        payment = Payment(
            user_id=user.id,
            provider=PaymentProvider.STARS.value,
            external_id=external_id,
            amount_sparks=amount_sparks,
            amount_rub=stars_paid,
            status=PaymentStatus.SUCCEEDED.value,
            purpose="buy_sparks",
            paid_at=paid_at,
        )
        session.add(payment)
        created += 1

    if created or updated:
        await session.flush()
        logger.info("Synced Stars payments: created=%s updated=%s", created, updated)
    return created + updated
