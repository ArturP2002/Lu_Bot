"""Точка входа бота LUMA."""

import asyncio
import logging
import sys

from redis.asyncio import Redis

from bot.app import create_bot, create_dispatcher, setup_bot_commands
from config import get_settings

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


async def main() -> None:
  settings = get_settings()
  if not settings.bot_token:
    logger.error("BOT_TOKEN не задан в .env")
    sys.exit(1)

  redis = Redis.from_url(settings.redis_url, decode_responses=True)
  bot = create_bot()
  dp = create_dispatcher(redis)
  await setup_bot_commands(bot)

  logger.info("Бот LUMA запущен (polling)")
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())
