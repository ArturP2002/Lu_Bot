"""Сборка и запуск бота."""

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, BotCommandScopeDefault, MenuButtonCommands
from redis.asyncio import Redis

from bot.handlers import admin, events, goals, luma, menu, payments, profile, rating, registration
from bot.middlewares.middlewares import (
  DatabaseMiddleware,
  PinMainMenuMiddleware,
  RedisMiddleware,
  ThrottleMiddleware,
  UserMiddleware,
)
from config import get_settings

logger = logging.getLogger(__name__)

BOT_COMMANDS = [
  BotCommand(command="start", description="🏠 Главное меню"),
]


def create_bot() -> Bot:
  settings = get_settings()
  return Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


async def setup_bot_commands(bot: Bot) -> None:
  """Боковое меню команд (кнопка Menu у поля ввода)."""
  await bot.set_my_commands(BOT_COMMANDS, scope=BotCommandScopeDefault())
  await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
  logger.info("Команды бокового меню установлены")


def create_dispatcher(redis: Redis) -> Dispatcher:
  storage = RedisStorage(redis=redis)
  dp = Dispatcher(storage=storage)

  dp.update.middleware(PinMainMenuMiddleware())
  dp.update.middleware(DatabaseMiddleware())
  dp.update.middleware(RedisMiddleware(redis))
  dp.update.middleware(UserMiddleware())
  dp.update.middleware(ThrottleMiddleware(redis))

  dp.include_router(registration.router)
  dp.include_router(admin.router)
  dp.include_router(menu.router)
  dp.include_router(profile.router)
  dp.include_router(rating.router)
  dp.include_router(goals.router)
  dp.include_router(events.router)
  dp.include_router(luma.router)
  dp.include_router(payments.router)

  return dp
