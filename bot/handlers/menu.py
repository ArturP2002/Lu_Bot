"""Главное меню."""

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import MenuButtonCommands, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.keyboards import limited_menu_kb, main_menu_kb
from bot.texts.i18n import lang_of, t
from bot.texts.ui_labels import all_menu_labels, resolve_menu_action, tx
from bot.utils.messaging import cleanup_reply_entry, replace_ui, send_ui
from models import User

router = Router()


async def send_menu(
  message: Message, user: User, redis: Redis | None = None, *, replace: bool = False
) -> None:
  """Отправить главное меню."""
  try:
    await message.bot.set_chat_menu_button(
      chat_id=message.chat.id,
      menu_button=MenuButtonCommands(),
    )
  except Exception:
    pass
  lang = lang_of(user)
  kb = main_menu_kb(lang) if user.verified else limited_menu_kb(lang)
  text = tx(user, "MENU_TITLE") if user.verified else t(user, "MENU_NEED_VERIFY")
  if replace:
    await replace_ui(message, text, reply_markup=kb, redis=redis)
  else:
    await send_ui(message, text, reply_markup=kb, redis=redis)


@router.message(Command("menu"))
@router.message(StateFilter("*"), F.text.in_(all_menu_labels("menu")))
async def cmd_menu(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  await state.clear()
  await cleanup_reply_entry(message, redis)
  await send_menu(message, user, redis=redis)


@router.message(StateFilter("*"), F.text.in_(all_menu_labels("profile")))
async def menu_profile(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  from bot.handlers.profile import show_profile
  await state.clear()
  await cleanup_reply_entry(message, redis)
  await show_profile(message, user, redis=redis)


@router.message(StateFilter("*"), F.text.in_(all_menu_labels("rate")))
async def menu_rate(message: Message, state: FSMContext, user: User, session: AsyncSession, redis: Redis) -> None:
  if not user.verified:
    await state.clear()
    await cleanup_reply_entry(message, redis)
    await send_ui(message, t(user, "MENU_NEED_VERIFY"), reply_markup=limited_menu_kb(lang_of(user)), redis=redis)
    return
  from bot.handlers.luma import clear_luma_browse
  from bot.handlers.rating import show_next_profile

  await state.clear()
  await cleanup_reply_entry(message, redis)
  await clear_luma_browse(redis, user.id)
  await show_next_profile(message, user, session, redis=redis)


@router.message(StateFilter("*"), F.text.in_(all_menu_labels("goals")))
async def menu_goals(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  if not user.verified:
    await state.clear()
    await cleanup_reply_entry(message, redis)
    await send_ui(message, t(user, "MENU_NEED_VERIFY"), reply_markup=limited_menu_kb(lang_of(user)), redis=redis)
    return
  from bot.handlers.goals import show_goal
  await state.clear()
  await cleanup_reply_entry(message, redis)
  await show_goal(message, user, redis=redis)


@router.message(StateFilter("*"), F.text.in_(all_menu_labels("events")))
async def menu_events(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  if not user.verified:
    await state.clear()
    await cleanup_reply_entry(message, redis)
    await send_ui(message, t(user, "MENU_NEED_VERIFY"), reply_markup=limited_menu_kb(lang_of(user)), redis=redis)
    return
  from bot.handlers.events import show_events_menu
  from bot.handlers.luma import clear_luma_browse

  await state.clear()
  await cleanup_reply_entry(message, redis)
  await clear_luma_browse(redis, user.id)
  await show_events_menu(message, user=user, redis=redis)


@router.message(StateFilter("*"), F.text.in_(all_menu_labels("luma")))
async def menu_luma(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  if not user.verified:
    await state.clear()
    await cleanup_reply_entry(message, redis)
    await send_ui(message, t(user, "MENU_NEED_VERIFY"), reply_markup=limited_menu_kb(lang_of(user)), redis=redis)
    return
  from bot.handlers.luma import show_luma
  await state.clear()
  await cleanup_reply_entry(message, redis)
  await show_luma(message, user, redis=redis)


# silence unused
_ = resolve_menu_action
