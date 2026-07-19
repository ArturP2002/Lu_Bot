"""Админ-панель (Mini App)."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.keyboards.keyboards import admin_webapp_kb
from bot.texts.i18n import t
from config import get_settings
from models import User

router = Router()


def is_telegram_admin(telegram_id: int | None) -> bool:
  """Проверка, что Telegram ID в списке администраторов."""
  if not telegram_id:
    return False
  return telegram_id in get_settings().admin_id_list


@router.message(Command("admin"))
async def cmd_admin(message: Message, user: User | None = None) -> None:
  tg_id = message.from_user.id if message.from_user else None
  lang_user = user or "ru"
  if not is_telegram_admin(tg_id):
    await message.answer(t(lang_user, "ADMIN_DENIED"))
    return

  settings = get_settings()
  if not settings.webapp_url or "your-domain" in settings.webapp_url:
    await message.answer(t(lang_user, "ADMIN_URL_MISSING"))
    return

  await message.answer(t(lang_user, "ADMIN_OPEN"), reply_markup=admin_webapp_kb())
