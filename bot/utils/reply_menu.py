"""Закрепление reply-клавиатуры главного меню."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from redis.asyncio import Redis

from bot.keyboards.keyboards import limited_menu_kb, main_menu_kb
from bot.texts.i18n import lang_of
from models import User

logger = logging.getLogger(__name__)

# Почти невидимый символ — Telegram отклоняет полностью пустой текст.
_MENU_PIN_SENTINEL = "\u2800"
MENU_ANCHOR_KEY = "menu:anchor:{chat_id}"
MENU_ANCHOR_TTL = 60 * 60 * 24 * 7

_PROFILE_EDIT_REPLY_STATES = frozenset(
    {
        "ProfileEdit:gender",
        "ProfileEdit:seeking",
        "ProfileEdit:visible_to",
    }
)


async def should_pin_main_menu(state: FSMContext | None) -> bool:
    """Не перебивать временные reply-клавиатуры регистрации и редактирования профиля."""
    if state is None:
        return True
    current = await state.get_state()
    if not current:
        return True
    if current.startswith("Registration:"):
        return False
    if current in _PROFILE_EDIT_REPLY_STATES:
        return False
    return True


async def pin_main_menu(
    bot: Bot,
    chat_id: int,
    user: User,
    redis: Redis | None = None,
) -> None:
    """Вернуть закреплённую reply-клавиатуру после inline-сообщений.

    Telegram не позволяет совместить inline- и reply-клавиатуру на одном сообщении.
    Отправляем служебное сообщение с меню и оставляем его (удаление снимает клавиатуру).
    """
    if not getattr(user, "profile_completed", False):
        return

    lang = lang_of(user)
    kb = main_menu_kb(lang) if getattr(user, "verified", False) else limited_menu_kb(lang)
    anchor_key = MENU_ANCHOR_KEY.format(chat_id=chat_id)

    try:
        new_msg = await bot.send_message(
            chat_id,
            _MENU_PIN_SENTINEL,
            reply_markup=kb,
            disable_notification=True,
        )
    except Exception as exc:
        logger.warning("pin_main_menu send failed chat=%s: %s", chat_id, exc)
        return

    if redis is not None:
        from bot.utils.messaging import safe_delete

        old_raw = await redis.get(anchor_key)
        await redis.set(anchor_key, str(new_msg.message_id), ex=MENU_ANCHOR_TTL)
        if old_raw:
            try:
                await safe_delete(bot=bot, chat_id=chat_id, message_id=int(old_raw))
            except Exception:
                pass
