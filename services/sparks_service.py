"""Сервис Искр и транзакций."""

from sqlalchemy.ext.asyncio import AsyncSession

from models import SparksTransaction, User
from services.user_service import is_premium


async def add_transaction(
    session: AsyncSession,
    user_id: int,
    amount: int,
    tx_type: str,
    reference_id: int | None = None,
    metadata: str | None = None,
) -> SparksTransaction:
    """Добавить запись в ledger и обновить баланс."""
    user = await session.get(User, user_id)
    if not user:
        raise ValueError("Пользователь не найден")

    user.sparks_balance += amount
    if user.sparks_balance < 0:
        raise ValueError("Недостаточно Искр")

    tx = SparksTransaction(
        user_id=user_id,
        amount=amount,
        tx_type=tx_type,
        reference_id=reference_id,
        metadata_json=metadata,
    )
    session.add(tx)
    await session.flush()
    return tx


async def support_goal(
    session: AsyncSession,
    sender: User,
    recipient: User,
    amount: int,
    is_anonymous: bool,
) -> tuple[int, int]:
    """Поддержка цели: списание с отправителя, зачисление получателю."""
    from sqlalchemy import select

    from models import Goal as GoalModel
    from models import Support
    from services.app_settings_service import get_setting_float

    fee_rate = 0.0 if is_premium(sender) else await get_setting_float(session, "support_fee_rate")
    fee = int(amount * fee_rate)
    total_debit = amount + fee

    if sender.sparks_balance < total_debit:
        raise ValueError("Недостаточно Искр для поддержки")

    await add_transaction(session, sender.id, -total_debit, "support_sent", recipient.id)
    await add_transaction(session, recipient.id, amount, "support_received", sender.id)

    session.add(
        Support(
            from_user_id=sender.id,
            to_user_id=recipient.id,
            amount=amount,
            fee=fee,
            is_anonymous=is_anonymous,
        )
    )

    result = await session.execute(select(GoalModel).where(GoalModel.user_id == recipient.id))
    goal = result.scalar_one_or_none()
    if goal:
        goal.collected_sparks += amount

    await session.flush()
    return amount, fee


async def withdraw_sparks(
    session: AsyncSession,
    user: User,
    amount: int,
    requisites: str | None = None,
    *,
    method: str = "requisites",
) -> tuple[int, int, int, int]:
    """Создать заявку на вывод. Возвращает (amount, fee, net, request_id)."""
    from services.app_settings_service import get_setting_float, get_setting_int

    method = (method or "requisites").strip().lower()
    if method not in ("stars", "requisites"):
        raise ValueError("Неверный способ вывода")

    requisites = (requisites or "").strip()
    if method == "requisites" and len(requisites) < 5:
        raise ValueError("Укажи реквизиты для перевода подробнее")
    if method == "stars" and not requisites:
        requisites = f"tg:{user.telegram_id}" + (f" @{user.username}" if user.username else "")

    withdraw_min = await get_setting_int(session, "withdraw_min")
    fee_rate = 0.07 if is_premium(user) else await get_setting_float(session, "withdraw_fee_rate")

    if amount < withdraw_min:
        raise ValueError(f"Минимальная сумма вывода — {withdraw_min} Искр")

    fee = int(amount * fee_rate)
    total_debit = amount
    net = amount - fee

    if user.sparks_balance < total_debit:
        raise ValueError("Недостаточно Искр")

    await add_transaction(session, user.id, -total_debit, "withdraw")
    if fee > 0:
        await add_transaction(session, user.id, 0, "withdraw_fee", metadata=str(fee))

    from models import WithdrawRequest

    req = WithdrawRequest(
        user_id=user.id,
        amount=amount,
        fee=fee,
        net_amount=net,
        method=method,
        requisites=requisites[:2000],
    )
    session.add(req)
    await session.flush()
    return amount, fee, net, req.id


async def transfer_goal_to_balance(session: AsyncSession, user: User) -> int:
    """Перевести накопленные на цели Искры на баланс."""
    from sqlalchemy import select
    from models import Goal as GoalModel

    result = await session.execute(select(GoalModel).where(GoalModel.user_id == user.id))
    goal = result.scalar_one_or_none()
    if not goal or goal.collected_sparks <= 0:
        raise ValueError("Нет Искр для перевода с цели")

    amount = goal.collected_sparks
    goal.collected_sparks = 0
    await add_transaction(session, user.id, amount, "goal_to_balance", goal.id)
    return amount


async def has_paid_event_fee(session: AsyncSession, user_id: int, event_id: int) -> bool:
    """Проверить, оплачен ли взнос за тусовку."""
    from sqlalchemy import select

    from models import SparksTransaction

    result = await session.execute(
        select(SparksTransaction.id).where(
            SparksTransaction.user_id == user_id,
            SparksTransaction.tx_type == "event_fee",
            SparksTransaction.reference_id == event_id,
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def pay_event_fee(
    session: AsyncSession,
    payer: User,
    organizer: User,
    event_id: int,
    amount: int,
) -> None:
    """Списать взнос с участника и зачислить организатору."""
    if amount <= 0:
        raise ValueError("Взнос не требуется")
    if payer.id == organizer.id:
        raise ValueError("Нельзя оплатить взнос самому себе")
    if await has_paid_event_fee(session, payer.id, event_id):
        raise ValueError("Взнос уже оплачен")
    if payer.sparks_balance < amount:
        raise ValueError("Недостаточно Искр")

    await add_transaction(session, payer.id, -amount, "event_fee", event_id)
    await add_transaction(
        session,
        organizer.id,
        amount,
        "event_fee_received",
        event_id,
        metadata=str(payer.id),
    )
