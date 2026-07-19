"""Начальные данные."""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from core.database import get_session_factory
from models import AppSetting, EventCategory
from services.event_service import TZ_CATEGORIES
import models  # noqa: F401


async def seed() -> None:
    factory = get_session_factory()
    async with factory() as session:
        if not await session.scalar(select(AppSetting).where(AppSetting.key == "ai_daily_limit")):
            session.add(AppSetting(key="ai_daily_limit", value="50"))

        # Обновляем категории под ТЗ
        for name, emoji, ftype in TZ_CATEGORIES:
            existing = await session.scalar(select(EventCategory).where(EventCategory.name == name))
            if existing:
                existing.emoji = emoji
                existing.filter_type = ftype
                existing.is_active = True
            else:
                session.add(EventCategory(name=name, emoji=emoji, filter_type=ftype))

        # Деактивируем лишние старые категории
        tz_names = {c[0] for c in TZ_CATEGORIES}
        result = await session.execute(select(EventCategory))
        for cat in result.scalars().all():
            if cat.name not in tz_names:
                cat.is_active = False

        await session.commit()
    print("Начальные данные загружены.")


if __name__ == "__main__":
    asyncio.run(seed())
