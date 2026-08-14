"""Хелперы отправки/редактирования/удаления UI-сообщений без захламления чата."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
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


def schedule_delete(message: Message | None, delay: float = 3.0) -> None:
  """Удалить сообщение через delay секунд, не блокируя обработчик."""
  if message is None:
    return
  bot = message.bot
  chat_id = message.chat.id
  message_id = message.message_id

  async def _run() -> None:
    await asyncio.sleep(delay)
    await safe_delete(bot=bot, chat_id=chat_id, message_id=message_id)

  asyncio.create_task(_run())


async def remember_ui_message(
  redis: Redis | None, chat_id: int, message_id: int | list[int] | tuple[int, ...]
) -> None:
  if redis is None:
    return
  if isinstance(message_id, int):
    value = str(message_id)
  else:
    value = ",".join(str(i) for i in message_id if i)
  if not value:
    return
  await redis.set(_ui_key(chat_id), value, ex=UI_MSG_TTL)


async def get_ui_message_ids(redis: Redis | None, chat_id: int) -> list[int]:
  if redis is None:
    return []
  raw = await redis.get(_ui_key(chat_id))
  if raw is None:
    return []
  text = raw.decode() if isinstance(raw, (bytes, bytearray)) else str(raw)
  ids: list[int] = []
  for part in text.split(","):
    part = part.strip()
    if part.isdigit():
      ids.append(int(part))
  return ids


async def get_ui_message_id(redis: Redis | None, chat_id: int) -> int | None:
  ids = await get_ui_message_ids(redis, chat_id)
  return ids[-1] if ids else None


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
  ids = await get_ui_message_ids(redis, chat_id)
  if not ids:
    return
  reply_menu_id = await get_reply_menu_message_id(redis, chat_id)
  for msg_id in ids:
    if reply_menu_id is not None and msg_id == reply_menu_id:
      continue
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


async def _track_many(redis: Redis | None, messages: list[Message]) -> Message | None:
  if not messages:
    return None
  if redis is not None:
    await remember_ui_message(redis, messages[0].chat.id, [m.message_id for m in messages])
  return messages[-1]


async def clear_reply_menu_tracking(redis: Redis | None, chat_id: int) -> None:
  """Сбросить метку носителя Reply-меню (например, перед регистрацией)."""
  if redis is None:
    return
  await redis.delete(_reply_menu_key(chat_id))


async def edit_ui(
  message: Message,
  text: str,
  *,
  message_id: int | None = None,
  reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | None = None,
  redis: Redis | None = None,
  parse_mode: str | None = None,
) -> Message | None:
  """Отредактировать UI-сообщение по id. Если нельзя — отправить новое.

  Возвращает Message, если появился новый пузырь (нужно обновить prompt_id).
  None — отредактировали существующий, id не менялся.
  """
  target_id = message_id or await get_ui_message_id(redis, message.chat.id)
  kwargs: dict[str, Any] = {"reply_markup": reply_markup}
  if parse_mode is not None:
    kwargs["parse_mode"] = parse_mode

  if target_id:
    try:
      edited = await message.bot.edit_message_text(
        text,
        chat_id=message.chat.id,
        message_id=target_id,
        **kwargs,
      )
      if isinstance(edited, Message):
        await _track(redis, edited)
        return None
      await remember_ui_message(redis, message.chat.id, target_id)
      return None
    except TelegramBadRequest as e:
      if "message is not modified" in str(e).lower():
        await remember_ui_message(redis, message.chat.id, target_id)
        return None
    except Exception:
      pass
    await safe_delete(bot=message.bot, chat_id=message.chat.id, message_id=target_id)

  return await send_ui(
    message,
    text,
    reply_markup=reply_markup,
    redis=redis,
    parse_mode=parse_mode,
  )


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
  """Заменить текущий UI-экран.

  Для Reply-клавиатуры сначала шлём новое сообщение с кнопками, потом удаляем
  старый экран — иначе клиент Telegram часто «теряет» клавиатуру.
  """
  if isinstance(reply_markup, ReplyKeyboardMarkup):
    old_ids = await get_ui_message_ids(redis, message.chat.id)
    sent = await send_ui(
      message,
      text,
      photo_file_id=photo_file_id,
      reply_markup=reply_markup,
      redis=redis,
      parse_mode=parse_mode,
      track=True,
    )
    reply_menu_id = await get_reply_menu_message_id(redis, message.chat.id)
    for old_id in old_ids:
      if sent is not None and old_id == sent.message_id:
        continue
      if reply_menu_id is not None and old_id == reply_menu_id:
        continue
      await safe_delete(bot=message.bot, chat_id=message.chat.id, message_id=old_id)
    return sent

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
  ids = await get_ui_message_ids(redis, message.chat.id)
  if len(ids) > 1:
    await delete_previous_ui(message.bot, redis, message.chat.id)
    return await send_ui(message, text, reply_markup=reply_markup, redis=redis, parse_mode=parse_mode)

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


async def send_profile_media(
  message: Message,
  text: str,
  media: list,
  *,
  reply_markup: InlineKeyboardMarkup | None = None,
  redis: Redis | None = None,
  parse_mode: str | None = None,
  edit: bool = True,
  track: bool = True,
) -> Message:
  """Показать анкету: одно фото/видео или медиагруппа."""
  from services.profile_media import ProfileMedia

  items: list[ProfileMedia] = list(media or [])
  if not items:
    return await edit_or_send(
      message,
      text,
      reply_markup=reply_markup,
      redis=redis,
      parse_mode=parse_mode,
      edit=edit,
      track=track,
    )

  ids = await get_ui_message_ids(redis, message.chat.id)
  can_inplace = (
    edit
    and message.from_user is not None
    and message.from_user.is_bot
    and len(items) == 1
    and len(ids) <= 1
    and (
      (items[0].kind == "photo" and bool(message.photo))
      or (items[0].kind == "video" and bool(message.video or message.animation))
    )
  )
  if can_inplace:
    cls = InputMediaPhoto if items[0].kind == "photo" else InputMediaVideo
    try:
      await message.edit_media(
        media=cls(media=items[0].file_id, caption=text, parse_mode=parse_mode or "HTML"),
        reply_markup=reply_markup,
      )
      if track:
        return await _track(redis, message)  # type: ignore[return-value]
      return message
    except Exception:
      logger.debug("inplace profile media edit failed", exc_info=True)

  await delete_previous_ui(message.bot, redis, message.chat.id)
  if edit and message.from_user and message.from_user.is_bot:
    if message.message_id not in ids:
      await safe_delete(message)

  return await _send_media_group_card(
    message,
    text,
    items,
    reply_markup=reply_markup,
    redis=redis,
    parse_mode=parse_mode,
    track=track,
  )


async def send_profile_media_chat(
  bot: Bot,
  chat_id: int,
  text: str,
  media: list,
  *,
  reply_markup: InlineKeyboardMarkup | None = None,
  parse_mode: str | None = None,
) -> None:
  """Отправить анкету в чат без контекста текущего UI-сообщения."""
  from services.profile_media import ProfileMedia

  items: list[ProfileMedia] = list(media or [])
  kwargs: dict[str, Any] = {"reply_markup": reply_markup}
  if parse_mode is not None:
    kwargs["parse_mode"] = parse_mode
  if not items:
    await bot.send_message(chat_id, text, **kwargs)
    return
  if len(items) == 1:
    item = items[0]
    if item.kind == "video":
      await bot.send_video(chat_id, item.file_id, caption=text, **kwargs)
    else:
      await bot.send_photo(chat_id, item.file_id, caption=text, **kwargs)
    return

  group = _input_media_list(items, text, parse_mode)
  msgs = await bot.send_media_group(chat_id, media=group)
  if reply_markup and msgs:
    try:
      await msgs[-1].edit_reply_markup(reply_markup=reply_markup)
    except Exception:
      await bot.send_message(chat_id, "⬇️", reply_markup=reply_markup)


def _input_media_list(items, text: str, parse_mode: str | None):
  group = []
  cap_mode = parse_mode if parse_mode is not None else "HTML"
  for i, item in enumerate(items):
    kwargs: dict[str, Any] = {}
    if i == 0:
      kwargs["caption"] = text
      kwargs["parse_mode"] = cap_mode
    if item.kind == "video":
      group.append(InputMediaVideo(media=item.file_id, **kwargs))
    else:
      group.append(InputMediaPhoto(media=item.file_id, **kwargs))
  return group


async def _send_media_group_card(
  message: Message,
  text: str,
  items,
  *,
  reply_markup: InlineKeyboardMarkup | None = None,
  redis: Redis | None = None,
  parse_mode: str | None = None,
  track: bool = True,
) -> Message:
  if len(items) == 1:
    item = items[0]
    kwargs: dict[str, Any] = {"caption": text, "reply_markup": reply_markup}
    if parse_mode is not None:
      kwargs["parse_mode"] = parse_mode
    try:
      if item.kind == "video":
        sent = await message.answer_video(item.file_id, **kwargs)
      else:
        sent = await message.answer_photo(item.file_id, **kwargs)
    except TelegramBadRequest as e:
      if _is_invalid_file_id_error(e):
        logger.warning("Invalid profile media file_id, fallback to text")
        sent = await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
      else:
        raise
    if track:
      return await _track(redis, sent)  # type: ignore[return-value]
    return sent

  group = _input_media_list(items, text, parse_mode)
  try:
    msgs = await message.answer_media_group(group)
  except TelegramBadRequest:
    logger.warning("send_media_group failed, fallback to first item", exc_info=True)
    return await _send_media_group_card(
      message,
      text,
      items[:1],
      reply_markup=reply_markup,
      redis=redis,
      parse_mode=parse_mode,
      track=track,
    )

  tracked = list(msgs)
  if reply_markup and msgs:
    try:
      await msgs[-1].edit_reply_markup(reply_markup=reply_markup)
    except Exception:
      extra = await message.answer("⬇️", reply_markup=reply_markup)
      tracked.append(extra)
  if track:
    return await _track_many(redis, tracked)  # type: ignore[return-value]
  return tracked[-1]


async def edit_or_send(
  message: Message,
  text: str,
  *,
  photo_file_id: str | None = None,
  media: list | None = None,
  reply_markup: InlineKeyboardMarkup | None = None,
  redis: Redis | None = None,
  parse_mode: str | None = None,
  edit: bool = True,
  track: bool = True,
  finalize_previous: bool = False,
) -> Message:
  """Edit текущего сообщения или отправить новый UI-экран."""
  if media is not None:
    return await send_profile_media(
      message,
      text,
      media,
      reply_markup=reply_markup,
      redis=redis,
      parse_mode=parse_mode,
      edit=edit,
      track=track,
    )
  if finalize_previous and message.from_user and message.from_user.is_bot:
    await strip_inline_keyboard(message)
  ids = await get_ui_message_ids(redis, message.chat.id)
  if len(ids) > 1:
    await delete_previous_ui(message.bot, redis, message.chat.id)
    return await send_ui(
      message,
      text,
      photo_file_id=photo_file_id,
      reply_markup=reply_markup,
      redis=redis,
      parse_mode=parse_mode,
      track=track,
    )
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
