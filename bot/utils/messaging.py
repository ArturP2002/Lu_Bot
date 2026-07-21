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

from bot.utils.menu_kb_flag import mark_menu_kb_attached

UI_MSG_KEY = "ui:msg:{chat_id}"
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


async def delete_previous_ui(bot: Bot, redis: Redis | None, chat_id: int) -> None:
  """Удалить предыдущий UI-экран бота и сбросить ключ."""
  msg_id = await get_ui_message_id(redis, chat_id)
  if msg_id is None:
    return
  await safe_delete(bot=bot, chat_id=chat_id, message_id=msg_id)
  if redis is not None:
    await redis.delete(_ui_key(chat_id))


async def cleanup_reply_entry(message: Message, redis: Redis | None) -> None:
  """При нажатии reply-кнопки: удалить сообщение пользователя и предыдущий UI."""
  await safe_delete(message)
  await delete_previous_ui(message.bot, redis, message.chat.id)


async def _track(redis: Redis | None, msg: Message | None) -> Message | None:
  if msg is not None and redis is not None:
    await remember_ui_message(redis, msg.chat.id, msg.message_id)
  return msg


def _maybe_mark_menu_kb(
  reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | None,
) -> None:
  if isinstance(reply_markup, ReplyKeyboardMarkup):
    mark_menu_kb_attached()


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
  _maybe_mark_menu_kb(reply_markup)
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
