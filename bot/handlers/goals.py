"""Раздел Цели."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.keyboards import goals_kb
from bot.states.states import GoalFlow
from bot.texts.i18n import lang_of, t
from bot.texts.ui_labels import service_err, tx
from bot.utils.messaging import cleanup_user_and_prompt, edit_or_send, safe_edit_text, send_ui
from models import Goal, User
from services.sparks_service import transfer_goal_to_balance

router = Router()


async def show_goal(
  message: Message,
  user: User,
  *,
  redis: Redis | None = None,
  edit: bool = False,
) -> None:
  goal = user.goal
  if not goal:
    text = tx(user, "NO_GOAL")
  else:
    remaining = max(0, goal.target_sparks - goal.collected_sparks)
    percent = int(100 * goal.collected_sparks / goal.target_sparks) if goal.target_sparks else 0
    text = t(
      user,
      "GOAL_SHOW",
      title=goal.title,
      collected=goal.collected_sparks,
      remaining=remaining,
      percent=min(100, percent),
    )
  await edit_or_send(message, text, reply_markup=goals_kb(lang_of(user)), redis=redis, edit=edit)


@router.callback_query(F.data == "goal:change")
async def goal_change_start(callback: CallbackQuery, state: FSMContext, user: User, redis: Redis) -> None:
    await state.set_state(GoalFlow.title)
    prompt = await safe_edit_text(callback.message, t(user, "GOAL_CHANGE_NAME"), redis=redis)
    await state.update_data(prompt_message_id=prompt.message_id if prompt else callback.message.message_id)
    await callback.answer()


@router.message(GoalFlow.title, F.text)
async def goal_change_title(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
    data = await state.get_data()
    await state.update_data(goal_title=message.text.strip()[:255])
    await state.set_state(GoalFlow.amount)
    await cleanup_user_and_prompt(message, prompt_message_id=data.get("prompt_message_id"))
    prompt = await send_ui(message, t(user, "GOAL_CHANGE_AMOUNT"), redis=redis)
    await state.update_data(prompt_message_id=prompt.message_id)


@router.message(GoalFlow.amount, F.text)
async def goal_change_amount(
    message: Message, state: FSMContext, user: User, session: AsyncSession, redis: Redis
) -> None:
    data = await state.get_data()
    prompt_id = data.get("prompt_message_id")
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer(t(user, "ERR_INVALID_INPUT"))
        return
    if user.goal:
        user.goal.title = data["goal_title"]
        user.goal.target_sparks = int(message.text)
        user.goal.collected_sparks = 0
    else:
        session.add(Goal(user_id=user.id, title=data["goal_title"], target_sparks=int(message.text)))
    await state.clear()
    await cleanup_user_and_prompt(message, prompt_message_id=prompt_id)
    await show_goal(message, user, redis=redis)


@router.callback_query(F.data == "goal:withdraw")
async def goal_withdraw(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
    try:
        amount = await transfer_goal_to_balance(session, user)
        await safe_edit_text(
            callback.message,
            tx(user, "SPARKS_TRANSFERRED", amount=amount),
            reply_markup=goals_kb(lang_of(user)),
            redis=redis,
        )
    except ValueError as e:
        await safe_edit_text(callback.message, service_err(user, e), reply_markup=goals_kb(lang_of(user)), redis=redis)
    await callback.answer()
