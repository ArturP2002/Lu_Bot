"""Главное меню."""

import logging

from aiogram import F, Router
from aiogram.filters import Command, Filter, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import MenuButtonCommands, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.texts.i18n import t
from bot.texts.ui_labels import resolve_menu_action, text_matches_menu_action, tx
from bot.utils.messaging import (
  cleanup_reply_entry,
  delete_previous_ui,
  ensure_reply_menu,
)
from models import User

router = Router()
logger = logging.getLogger(__name__)


class MenuAction(Filter):
  """Матч reply-кнопки по корню текста (эмодзи/пробелы не важны)."""

  def __init__(self, action: str) -> None:
    self.action = action

  async def __call__(self, message: Message) -> bool:
    return text_matches_menu_action(message.text, self.action)


async def send_menu(
  message: Message, user: User, redis: Redis | None = None, *, replace: bool = False
) -> None:
  """Отправить главное меню (оно же — носитель Reply-клавиатуры)."""
  try:
    await message.bot.set_chat_menu_button(
      chat_id=message.chat.id,
      menu_button=MenuButtonCommands(),
    )
  except Exception:
    pass
  text = tx(user, "MENU_TITLE")
  if replace:
    await delete_previous_ui(message.bot, redis, message.chat.id)
  await ensure_reply_menu(message, user, redis, text=text, force=True)


async def _open_from_menu(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  """Сброс FSM, удаление прошлых экранов, закрепление Reply-меню."""
  await state.clear()
  await cleanup_reply_entry(message, redis)
  await ensure_reply_menu(message, user, redis)


@router.message(Command("menu"))
@router.message(MenuAction("menu"))
@router.message(StateFilter("*"), MenuAction("menu"))
async def cmd_menu(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  await state.clear()
  await cleanup_reply_entry(message, redis)
  await send_menu(message, user, redis=redis)


@router.message(MenuAction("profile"))
@router.message(StateFilter("*"), MenuAction("profile"))
async def menu_profile(
  message: Message, state: FSMContext, user: User, session: AsyncSession, redis: Redis
) -> None:
  from bot.handlers.profile import show_profile
  await _open_from_menu(message, state, user, redis)
  await show_profile(message, user, session=session, redis=redis)


@router.message(MenuAction("rate"))
@router.message(StateFilter("*"), MenuAction("rate"))
async def menu_rate(message: Message, state: FSMContext, user: User, session: AsyncSession, redis: Redis) -> None:
  from bot.handlers.luma import clear_luma_browse
  from bot.handlers.rating import show_next_profile
  from services.like_inbox_service import set_inbox_browsing

  logger.info(
    "menu_rate hit telegram_id=%s text=%r",
    getattr(user, "telegram_id", None),
    message.text,
  )
  await _open_from_menu(message, state, user, redis)
  await clear_luma_browse(redis, user.id)
  await set_inbox_browsing(redis, user.id, False)
  try:
    await show_next_profile(message, user, session, redis=redis, allow_feed_reset=True)
  except Exception as e:
    logger.exception(
      "menu_rate show_next_profile failed telegram_id=%s err=%s: %s",
      user.telegram_id,
      type(e).__name__,
      e,
    )
    try:
      await message.answer(
        "Не удалось открыть ленту. Попробуй ещё раз через пару секунд."
      )
    except Exception:
      logger.exception("menu_rate fallback failed telegram_id=%s", user.telegram_id)


@router.message(MenuAction("goals"))
@router.message(StateFilter("*"), MenuAction("goals"))
async def menu_goals(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  from bot.handlers.goals import show_goal
  await _open_from_menu(message, state, user, redis)
  await show_goal(message, user, redis=redis)


@router.message(MenuAction("events"))
@router.message(StateFilter("*"), MenuAction("events"))
async def menu_events(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  from bot.handlers.events import show_events_menu
  from bot.handlers.luma import clear_luma_browse

  await _open_from_menu(message, state, user, redis)
  await clear_luma_browse(redis, user.id)
  await show_events_menu(message, user=user, redis=redis)


@router.message(MenuAction("luma"))
@router.message(StateFilter("*"), MenuAction("luma"))
async def menu_luma(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  from bot.handlers.luma import show_luma
  await _open_from_menu(message, state, user, redis)
  await show_luma(message, user, redis=redis)


# silence unused
_ = (resolve_menu_action, F)
