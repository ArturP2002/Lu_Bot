"""Интеграция с ЮKassa: реальные платежи или заглушка без кредов."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models import Payment, User
from models.entities import PaymentProvider, PaymentStatus
from services.sparks_service import add_transaction

logger = logging.getLogger(__name__)
settings = get_settings()

YOOKASSA_API = "https://api.yookassa.ru/v3/payments"


@dataclass
class PaymentLink:
    """Ссылка на оплату."""

    payment: Payment
    confirmation_url: str
    is_stub: bool


async def rub_amount_for_sparks(session: AsyncSession, sparks: int) -> float:
    """Сумма в рублях за покупку искр."""
    from services.app_settings_service import get_setting_float

    price = await get_setting_float(session, "spark_price_rub")
    return round(sparks * price, 2)


async def create_yookassa_payment(
    session: AsyncSession,
    user: User,
    amount_sparks: int,
    *,
    purpose: str = "buy_sparks",
    description: str | None = None,
) -> PaymentLink:
    """Создать платёж ЮKassa. Без кредов — заглушка со stub-ссылкой."""
    if amount_sparks <= 0:
        raise ValueError("Сумма должна быть больше 0")

    amount_rub = await rub_amount_for_sparks(session, amount_sparks)
    description = description or f"Покупка {amount_sparks} Искр (LUMO)"

    from services.app_settings_service import get_setting_bool

    # Stub, если нет кредов ИЛИ админ включил демо-режим
    force_stub = await get_setting_bool(session, "yookassa_stub_enabled")
    use_real = settings.yookassa_configured and not force_stub

    payment = Payment(
        user_id=user.id,
        provider=PaymentProvider.YOOKASSA.value,
        amount_sparks=amount_sparks,
        amount_rub=amount_rub,
        status=PaymentStatus.PENDING.value,
        purpose=purpose,
        is_stub=not use_real,
    )
    session.add(payment)
    await session.flush()

    if use_real:
        external_id, url = await _create_real_payment(
            payment_id=payment.id,
            user_id=user.id,
            amount_rub=amount_rub,
            amount_sparks=amount_sparks,
            purpose=purpose,
            description=description,
        )
        payment.external_id = external_id
        payment.confirmation_url = url
        payment.is_stub = False
    else:
        stub_id = f"stub-{payment.id}-{uuid.uuid4().hex[:8]}"
        payment.external_id = stub_id
        payment.confirmation_url = f"https://yookassa.ru/demo-checkout/{stub_id}"
        payment.is_stub = True
        reason = "нет YOOKASSA_SHOP_ID / YOOKASSA_SHOP_SECRET_ID" if not settings.yookassa_configured else "включён демо-stub в настройках"
        logger.warning("ЮKassa: заглушка (%s), payment_id=%s", reason, payment.id)

    await session.flush()
    return PaymentLink(
        payment=payment,
        confirmation_url=payment.confirmation_url or "",
        is_stub=payment.is_stub,
    )


async def _create_real_payment(
    *,
    payment_id: int,
    user_id: int,
    amount_rub: float,
    amount_sparks: int,
    purpose: str,
    description: str,
) -> tuple[str, str]:
    """Создать платёж через API ЮKassa, вернуть (external_id, confirmation_url)."""
    return_url = settings.yookassa_return_url.strip() or f"https://t.me/{settings.bot_username}"
    payload = {
        "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": description[:128],
        "metadata": {
            "payment_id": str(payment_id),
            "user_id": str(user_id),
            "amount_sparks": str(amount_sparks),
            "purpose": purpose,
        },
    }
    idempotence_key = str(uuid.uuid4())

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            YOOKASSA_API,
            auth=(settings.yookassa_shop_id, settings.yookassa_shop_secret_id),
            headers={"Idempotence-Key": idempotence_key, "Content-Type": "application/json"},
            json=payload,
        )

    if response.status_code >= 400:
        logger.error("ЮKassa create payment failed: %s %s", response.status_code, response.text)
        raise ValueError("Не удалось создать платёж ЮKassa. Попробуй позже.")

    data = response.json()
    confirmation = data.get("confirmation") or {}
    url = confirmation.get("confirmation_url")
    external_id = data.get("id")
    if not url or not external_id:
        raise ValueError("ЮKassa не вернула ссылку на оплату")
    return external_id, url


async def fetch_yookassa_payment_status(external_id: str) -> str | None:
    """Получить статус платежа из API ЮKassa."""
    if not settings.yookassa_configured or external_id.startswith("stub-"):
        return None

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{YOOKASSA_API}/{external_id}",
            auth=(settings.yookassa_shop_id, settings.yookassa_shop_secret_id),
        )
    if response.status_code >= 400:
        logger.error("ЮKassa get payment failed: %s %s", response.status_code, response.text)
        return None
    return response.json().get("status")


async def complete_payment(
    session: AsyncSession,
    payment: Payment,
    *,
    allow_stub: bool = False,
) -> bool:
    """Зачислить искр по успешному платежу. Идемпотентно. Возвращает True, если зачисление новое."""
    if payment.status == PaymentStatus.SUCCEEDED.value:
        return False
    if payment.is_stub and not allow_stub:
        raise ValueError("Stub-платёж нельзя подтвердить через вебхук")

    payment.status = PaymentStatus.SUCCEEDED.value
    payment.paid_at = datetime.now(timezone.utc)
    await add_transaction(
        session,
        payment.user_id,
        payment.amount_sparks,
        "purchase",
        reference_id=payment.id,
        metadata=f"yookassa:{payment.external_id}",
    )
    # Комиссия блогеру 20% от покупки (в искрах от суммы покупки)
    user = await session.get(User, payment.user_id)
    if user:
        from services.blogger_service import pay_blogger_commission

        await pay_blogger_commission(session, user, payment.amount_sparks, purpose="buy_sparks")
    return True


async def get_payment_by_external_id(session: AsyncSession, external_id: str) -> Payment | None:
    result = await session.execute(select(Payment).where(Payment.external_id == external_id))
    return result.scalar_one_or_none()


async def handle_yookassa_webhook(session: AsyncSession, payload: dict) -> tuple[Payment | None, bool]:
    """Обработать уведомление ЮKassa. Возвращает (payment, newly_credited)."""
    event = payload.get("event")
    obj = payload.get("object") or {}
    external_id = obj.get("id")
    if not external_id:
        return None, False

    payment = await get_payment_by_external_id(session, external_id)
    if not payment:
        # Fallback по metadata.payment_id
        meta = obj.get("metadata") or {}
        raw_id = meta.get("payment_id")
        if raw_id and str(raw_id).isdigit():
            payment = await session.get(Payment, int(raw_id))
    if not payment:
        logger.warning("ЮKassa webhook: платёж не найден %s", external_id)
        return None, False

    if not payment.external_id:
        payment.external_id = external_id

    status = obj.get("status")
    newly_credited = False
    if event == "payment.succeeded" or status == "succeeded":
        newly_credited = await complete_payment(session, payment, allow_stub=False)
    elif event == "payment.canceled" or status == "canceled":
        if payment.status == PaymentStatus.PENDING.value:
            payment.status = PaymentStatus.CANCELED.value
    return payment, newly_credited
