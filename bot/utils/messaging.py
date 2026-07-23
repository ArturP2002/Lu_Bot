"""Хелперы отправки/редактирования/удаления UI-сообщений без захламления чата."""

from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from redis.asyncio import Redis

UI_MSG_KEY = "ui:msg:{chat_id}"
REPLY_MENU_MSG_KEY = "ui:reply_menu:{chat_id}"
UI_MSG_TTL = 60 * 60 * 24 * 7  # 7 дней

logger = logging.getLogger(__name__)


def _is_invalid_file_id_error(exc: Exception) -> bool:
  if not isinstance(exc, TelegramBadRequest):
    return False
  msg = str(exc).lower()
  markers = (
    "wrong file identifier",
    "wrong file_id",
    "http url specified",
    "file is temporarily unavailable",
    "file not found",
  )
  return any(marker in msg for marker in markers)


def _ui_key(chat_id: int) -> str:
  return UI_MSG_KEY.format(chat_id=chat_id)


def _reply_menu_key(chat_id: int) -> str:
  return REPLY_MENU_MSG_KEY.format(chat_id=chat_id)


async def safe_delete(
  message: Message | None = None,
  *,
  bot: Bot | None = None,
  chat_id: int | None = None,
  message_id: int | None = None,
) -> None:
  """Удалить сообщение, игнорируя ошибки Telegram."""
  try:
    if message is not None:
      await message.delete()
      return
    if bot is not None and chat_id is not None and message_id is not None:
      await bot.delete_message(chat_id, message_id)
  except Exception:
    pass


async def remember_ui_message(redis: Redis | None, chat_id: int, message_id: int) -> None:
  if redis is None:
    return
  await redis.set(_ui_key(chat_id), str(message_id), ex=UI_MSG_TTL)


async def get_ui_message_id(redis: Redis | None, chat_id: int) -> int | None:
  if redis is None:
    return None
  raw = await redis.get(_ui_key(chat_id))
  if raw is None:
    return None
  try:
    return int(raw)
  except (TypeError, ValueError):
    return None


async def remember_reply_menu_message(redis: Redis | None, chat_id: int, message_id: int) -> None:
  """Сообщение-носитель Reply-меню — его нельзя удалять при смене экранов."""
  if redis is None:
    return
  await redis.set(_reply_menu_key(chat_id), str(message_id), ex=UI_MSG_TTL)


async def get_reply_menu_message_id(redis: Redis | None, chat_id: int) -> int | None:
  if redis is None:
    return None
  raw = await redis.get(_reply_menu_key(chat_id))
  if raw is None:
    return None
  try:
    return int(raw)
  except (TypeError, ValueError):
    return None


async def delete_previous_ui(bot: Bot, redis: Redis | None, chat_id: int) -> None:
  """Удалить предыдущий UI-экран бота (не трогая носитель Reply-меню)."""
  msg_id = await get_ui_message_id(redis, chat_id)
  if msg_id is None:
    return
  reply_menu_id = await get_reply_menu_message_id(redis, chat_id)
  if reply_menu_id is not None and msg_id == reply_menu_id:
    # Носитель клавиатуры не удаляем — только снимаем UI-метку
    if redis is not None:
      await redis.delete(_ui_key(chat_id))
    return
  await safe_delete(bot=bot, chat_id=chat_id, message_id=msg_id)
  if redis is not None:
    await redis.delete(_ui_key(chat_id))


async def cleanup_reply_entry(message: Message, redis: Redis | None) -> None:
  """При нажатии reply-кнопки: удалить сообщение пользователя и предыдущий UI-экран.

  Удаляется 2 сообщения: (1) нажатие пользователя, (2) прошлый контент-экран.
  Носитель Reply-меню не удаляется.
  """
  await safe_delete(message)
  await delete_previous_ui(message.bot, redis, message.chat.id)


async def ensure_reply_menu(
  message: Message,
  user,
  redis: Redis | None = None,
  *,
  text: str | None = None,
  force: bool = False,
) -> Message | None:
  """Держать в чате сообщение-носитель Reply-меню (не удалять его при навигации).

  Если носитель уже есть и force=False — ничего не шлём (клавиатура уже закреплена).
  Если force=True или носителя нет — шлём новое с меню, старое удаляем после.
  """
  from bot.keyboards.keyboards import menu_kb_for

  chat_id = message.chat.id
  old_id = await get_reply_menu_message_id(redis, chat_id)
  if old_id is not None and not force and text is None:
    return None

  body = text
  if body is None:
    from bot.texts.i18n import t
    from bot.texts.ui_labels import tx

    body = tx(user, "MENU_TITLE") if getattr(user, "verified", False) else t(user, "MENU_NEED_VERIFY")

  try:
    sent = await message.answer(body, reply_markup=menu_kb_for(user))
  except Exception:
    logger.debug("ensure_reply_menu failed", exc_info=True)
    return None

  await remember_reply_menu_message(redis, chat_id, sent.message_id)
  if old_id is not None and old_id != sent.message_id:
    await safe_delete(bot=message.bot, chat_id=chat_id, message_id=old_id)
    # если старый носитель ошибочно числился как UI — очистим
    ui_id = await get_ui_message_id(redis, chat_id)
    if ui_id is not None and ui_id == old_id and redis is not None:
      await redis.delete(_ui_key(chat_id))
  return sent


async def _track(redis: Redis | None, msg: Message | None) -> Message | None:
  if msg is not None and redis is not None:
    await remember_ui_message(redis, msg.chat.id, msg.message_id)
  return msg


async def send_ui(
  message: Message,
  text: str,
  *,
  photo_file_id: str | None = None,
  reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | None = None,
  redis: Redis | None = None,
  parse_mode: str | None = None,
  track: bool = True,
) -> Message:
  """Отправить новый UI-экран и опционально запомнить message_id."""
  kwargs: dict[str, Any] = {"reply_markup": reply_markup}
  if parse_mode is not None:
    kwargs["parse_mode"] = parse_mode
  if photo_file_id:
    try:
      sent = await message.answer_photo(photo_file_id, caption=text, **kwargs)
    except TelegramBadRequest as e:
      if _is_invalid_file_id_error(e):
        logger.warning("Invalid photo file_id, fallback to text: %s...", photo_file_id[:24])
        sent = await message.answer(text, **kwargs)
      else:
        raise
  else:
    sent = await message.answer(text, **kwargs)
  if track:
    return await _track(redis, sent)  # type: ignore[return-value]
  return sent


async def replace_ui(
  message: Message,
  text: str,
  *,
  photo_file_id: str | None = None,
  reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | None = None,
  redis: Redis | None = None,
  parse_mode: str | None = None,
) -> Message:
  """Заменить текущий UI-экран (удалить предыдущий и отправить новый)."""
  await delete_previous_ui(message.bot, redis, message.chat.id)
  return await send_ui(
    message,
    text,
    photo_file_id=photo_file_id,
    reply_markup=reply_markup,
    redis=redis,
    parse_mode=parse_mode,
    track=True,
  )


async def strip_inline_keyboard(message: Message) -> None:
  """Убрать inline-кнопки, оставив текст/фото сообщения."""
  try:
    await message.edit_reply_markup(reply_markup=None)
  except Exception:
    pass


async def resolve_photo_file_id(bot: Bot, user) -> str | None:
  """Проверить file_id фото; сбросить в БД, если он недействителен для этого бота."""
  fid = getattr(user, "photo_file_id", None)
  if not fid:
    return None
  try:
    await bot.get_file(fid)
    return fid
  except TelegramBadRequest as e:
    logger.warning(
      "Clearing invalid photo_file_id for user %s: %s",
      getattr(user, "id", "?"),
      e,
    )
    user.photo_file_id = None
    return None
  except Exception as e:
    logger.warning(
      "Cannot verify photo_file_id for user %s, sending without photo: %s",
      getattr(user, "id", "?"),
      e,
    )
    return None


async def safe_edit_text(
  message: Message,
  text: str,
  *,
  reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | None = None,
  redis: Redis | None = None,
  parse_mode: str | None = None,
) -> Message:
  """Отредактировать текст сообщения; при ошибке — удалить и отправить заново.

  Если исходное сообщение с фото — удаляем его и шлём текстовый экран
  (Telegram не умеет убрать медиа через edit).
  """
  kwargs: dict[str, Any] = {"reply_markup": reply_markup}
  if parse_mode is not None:
    kwargs["parse_mode"] = parse_mode

  # Фото нельзя убрать через edit — пересоздаём текстом
  if message.photo or message.video or message.document or message.animation:
    await safe_delete(message)
    return await send_ui(message, text, reply_markup=reply_markup, redis=redis, parse_mode=parse_mode)

  try:
    await message.edit_text(text, **kwargs)
    return await _track(redis, message)  # type: ignore[return-value]
  except TelegramBadRequest as e:
    if "message is not modified" in str(e).lower():
      return await _track(redis, message)  # type: ignore[return-value]
  except Exception:
    pass

  await safe_delete(message)
  return await send_ui(message, text, reply_markup=reply_markup, redis=redis, parse_mode=parse_mode)


async def safe_edit_media(
  message: Message,
  text: str,
  photo_file_id: str | None = None,
  *,
  reply_markup: InlineKeyboardMarkup | None = None,
  redis: Redis | None = None,
  parse_mode: str | None = None,
) -> Message:
  """Отредактировать карточку (фото/текст). Fallback — delete + send."""
  kwargs: dict[str, Any] = {"reply_markup": reply_markup}
  if parse_mode is not None:
    kwargs["parse_mode"] = parse_mode

  try:
    if photo_file_id:
      media = InputMediaPhoto(media=photo_file_id, caption=text, parse_mode=parse_mode)
      try:
        await message.edit_media(media=media, reply_markup=reply_markup)
        return await _track(redis, message)  # type: ignore[return-value]
      except TelegramBadRequest as e:
        if not _is_invalid_file_id_error(e):
          raise
        logger.warning("Invalid photo file_id on edit, fallback to text: %s...", photo_file_id[:24])
        photo_file_id = None

    if message.photo:
      await safe_delete(message)
      return await send_ui(message, text, reply_markup=reply_markup, redis=redis, parse_mode=parse_mode)

    await message.edit_text(text, **kwargs)
    return await _track(redis, message)  # type: ignore[return-value]
  except TelegramBadRequest as e:
    if "message is not modified" in str(e).lower():
      return await _track(redis, message)  # type: ignore[return-value]
  except Exception:
    pass

  await safe_delete(message)
  return await send_ui(
    message,
    text,
    photo_file_id=photo_file_id,
    reply_markup=reply_markup,
    redis=redis,
    parse_mode=parse_mode,
  )


async def edit_or_send(
  message: Message,
  text: str,
  *,
  photo_file_id: str | None = None,
  reply_markup: InlineKeyboardMarkup | None = None,
  redis: Redis | None = None,
  parse_mode: str | None = None,
  edit: bool = True,
  track: bool = True,
  finalize_previous: bool = False,
) -> Message:
  """Edit текущего сообщения или отправить новый UI-экран."""
  if finalize_previous and message.from_user and message.from_user.is_bot:
    await strip_inline_keyboard(message)
  if edit and message.from_user and message.from_user.is_bot:
    return await safe_edit_media(
      message,
      text,
      photo_file_id,
      reply_markup=reply_markup,
      redis=redis,
      parse_mode=parse_mode,
    )
  return await send_ui(
    message,
    text,
    photo_file_id=photo_file_id,
    reply_markup=reply_markup,
    redis=redis,
    parse_mode=parse_mode,
    track=track,
  )


async def cleanup_user_and_prompt(
  user_message: Message,
  *,
  prompt_message_id: int | None = None,
) -> None:
  """Удалить ответ пользователя и промпт бота после FSM-ввода."""
  chat_id = user_message.chat.id
  bot = user_message.bot
  await safe_delete(user_message)
  if prompt_message_id is not None:
    await safe_delete(bot=bot, chat_id=chat_id, message_id=prompt_message_id)
