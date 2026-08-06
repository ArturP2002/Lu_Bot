"""Обработчики платежей: Telegram Stars + ЮKassa."""

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.texts.i18n import t
from bot.texts.ui_labels import tx
from bot.utils.messaging import safe_edit_text, send_ui
from models import Payment, User
from models.entities import PaymentStatus
from services.yookassa_service import complete_payment, fetch_yookassa_payment_status

router = Router()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
  """Подтверждение перед оплатой Telegram Stars."""
  await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message, user: User, session: AsyncSession, redis: Redis) -> None:
  """Успешная оплата через Telegram Stars."""
  from datetime import datetime, timezone

  from services.stars_payment_service import parse_buy_sparks_amount, record_stars_payment

  sp = message.successful_payment
  if not sp:
    return

  amount_sparks = parse_buy_sparks_amount(sp.invoice_payload, sp.total_amount)
  external_id = sp.telegram_payment_charge_id or sp.provider_payment_charge_id
  if not external_id:
    external_id = f"stars:{message.from_user.id}:{sp.total_amount}:{int(datetime.now(timezone.utc).timestamp())}"

  await record_stars_payment(
    session,
    user,
    external_id=external_id,
    amount_sparks=amount_sparks,
    paid_at=datetime.now(timezone.utc),
    credit_balance=True,
  )
  await send_ui(message, t(user, "PAY_SUCCESS", amount=amount_sparks), redis=redis)


@router.callback_query(F.data.startswith("pay:stub:"))
async def pay_stub_confirm(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  """Демо-зачисление, пока ЮKassa без реальных кредов."""
  payment_id = int(callback.data.split(":")[-1])
  payment = await session.get(Payment, payment_id)
  if not payment or payment.user_id != user.id:
    await callback.answer(t(user, "PAY_NOT_FOUND"), show_alert=True)
    return
  if not payment.is_stub:
    await callback.answer(tx(user, "PAY_NOT_STUB"), show_alert=True)
    return
  if payment.status == PaymentStatus.SUCCEEDED.value:
    await callback.answer(tx(user, "PAY_ALREADY"), show_alert=True)
    return

  await complete_payment(session, payment, allow_stub=True)
  await safe_edit_text(
    callback.message,
    t(user, "PAY_SUCCESS", amount=payment.amount_sparks),
    redis=redis,
  )
  await callback.answer()


@router.callback_query(F.data.startswith("pay:check:"))
async def pay_check(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  """Проверить статус оплаты ЮKassa вручную."""
  payment_id = int(callback.data.split(":")[-1])
  payment = await session.get(Payment, payment_id)
  if not payment or payment.user_id != user.id:
    await callback.answer(t(user, "PAY_NOT_FOUND"), show_alert=True)
    return

  if payment.status == PaymentStatus.SUCCEEDED.value:
    await callback.answer(tx(user, "PAY_ALREADY"), show_alert=True)
    return
  if payment.status == PaymentStatus.CANCELED.value:
    await callback.answer(t(user, "PAY_CANCELED"), show_alert=True)
    return

  status = None
  if payment.external_id:
    status = await fetch_yookassa_payment_status(payment.external_id)

  if status == "succeeded":
    await complete_payment(session, payment, allow_stub=False)
    await safe_edit_text(
      callback.message,
      t(user, "PAY_SUCCESS", amount=payment.amount_sparks),
      redis=redis,
    )
    await callback.answer()
    return

  if status == "canceled":
    payment.status = PaymentStatus.CANCELED.value
    await callback.answer(t(user, "PAY_CANCELED"), show_alert=True)
    return

  await callback.answer(t(user, "PAY_PENDING"), show_alert=True)
