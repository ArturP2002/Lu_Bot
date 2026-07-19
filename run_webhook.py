"""Запуск бота в режиме webhook (продакшен)."""

import asyncio
import logging
import sys

from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from redis.asyncio import Redis

from bot.app import create_bot, create_dispatcher, setup_bot_commands
from config import get_settings

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    if not settings.webhook_url:
        logger.error("WEBHOOK_URL не задан")
        sys.exit(1)

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    bot = create_bot()
    dp = create_dispatcher(redis)
    await setup_bot_commands(bot)

    app = web.Application()
    webhook_path = "/webhook"
    handler = SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=settings.webhook_secret or None)
    handler.register(app, path=webhook_path)
    setup_application(app, dp, bot=bot)

    await bot.set_webhook(
        url=f"{settings.webhook_url}{webhook_path}",
        secret_token=settings.webhook_secret or None,
    )

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    logger.info("Webhook сервер запущен на :8080")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
