"""Закрепление reply-клавиатуры главного меню."""

from aiogram import Bot
from aiogram.fsm.context import FSMContext

from bot.keyboards.keyboards import limited_menu_kb, main_menu_kb
from bot.texts.i18n import lang_of
from bot.utils.messaging import safe_delete
from models import User

_MENU_PIN_SENTINEL = "\u200b"

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


async def pin_main_menu(bot: Bot, chat_id: int, user: User) -> None:
    """Вернуть закреплённую reply-клавиатуру после inline-сообщений.

    Telegram не позволяет совместить inline- и reply-клавиатуру на одном сообщении,
    поэтому отправляем служебное сообщение с меню и сразу удаляем его — клавиатура остаётся.
    """
    if not getattr(user, "profile_completed", False):
        return
    lang = lang_of(user)
    kb = main_menu_kb(lang) if getattr(user, "verified", False) else limited_menu_kb(lang)
    try:
        tmp = await bot.send_message(
            chat_id,
            _MENU_PIN_SENTINEL,
            reply_markup=kb,
            disable_notification=True,
        )
        await safe_delete(bot=bot, chat_id=chat_id, message_id=tmp.message_id)
    except Exception:
        pass
