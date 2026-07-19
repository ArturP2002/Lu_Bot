"""Чтение/запись динамических настроек приложения (AppSetting)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models import AppSetting


def env_defaults() -> dict[str, str]:
    """Актуальные значения из .env / config (не кэшируются на уровне модуля)."""
    s = get_settings()
    return {
        "ai_daily_limit": str(s.ai_daily_limit),
        "spark_price_rub": str(s.spark_price_rub),
        "spark_price_stars": str(s.spark_price_stars),
        "premium_price": str(s.premium_price),
        "rating_reset_price": str(s.rating_reset_price),
        "withdraw_min": str(s.withdraw_min),
        "withdraw_fee_rate": str(s.withdraw_fee_rate),
        "support_fee_rate": str(s.support_fee_rate),
        "rules_link_1": s.rules_link_1,
        "rules_link_2": s.rules_link_2,
        "yookassa_stub_enabled": "1",
        "feed_filter_seeking": "1",
        "feed_filter_visible_to": "0",
        "feed_filter_city": "0",
    }


# Совместимость со старым импортом DEFAULTS через __getattr__
def __getattr__(name: str):
    if name == "DEFAULTS":
        return env_defaults()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


SETTING_META: list[dict] = [
    {
        "key": "spark_price_rub",
        "label": "1 Искра = ₽",
        "hint": "Курс ЮKassa",
        "type": "float",
        "group": "pricing",
    },
    {
        "key": "spark_price_stars",
        "label": "1 Искра = Stars",
        "hint": "Курс Telegram Stars",
        "type": "float",
        "group": "pricing",
    },
    {
        "key": "premium_price",
        "label": "Цена Premium (Искры)",
        "hint": "Стоимость Premium в Искрах",
        "type": "int",
        "group": "pricing",
    },
    {
        "key": "rating_reset_price",
        "label": "Сброс рейтинга (Искры)",
        "hint": "Стоимость сброса рейтинга",
        "type": "int",
        "group": "pricing",
    },
    {
        "key": "withdraw_min",
        "label": "Мин. вывод (Искры)",
        "hint": "Минимальная сумма заявки на вывод",
        "type": "int",
        "group": "fees",
    },
    {
        "key": "withdraw_fee_rate",
        "label": "Комиссия вывода",
        "hint": "Доля, например 0.1 = 10%",
        "type": "float",
        "group": "fees",
    },
    {
        "key": "support_fee_rate",
        "label": "Комиссия поддержки цели",
        "hint": "Для пользователей без Premium",
        "type": "float",
        "group": "fees",
    },
    {
        "key": "ai_daily_limit",
        "label": "Лимит AI в сутки",
        "hint": "Запросов к LUMA AI на Premium-пользователя",
        "type": "int",
        "group": "limits",
    },
    {
        "key": "feed_filter_seeking",
        "label": "Фильтр «кого оценивать»",
        "hint": "Учитывать выбор «кого оценивать» в ленте (пол анкет)",
        "type": "bool",
        "group": "feed",
    },
    {
        "key": "feed_filter_visible_to",
        "label": "Фильтр «кому показывать»",
        "hint": "Учитывать, кому кандидат разрешил показывать анкету",
        "type": "bool",
        "group": "feed",
    },
    {
        "key": "feed_filter_city",
        "label": "Фильтр по городу",
        "hint": "Показывать только анкеты из того же города",
        "type": "bool",
        "group": "feed",
    },
    {
        "key": "rules_link_1",
        "label": "Ссылка на правила",
        "hint": "",
        "type": "url",
        "group": "links",
    },
    {
        "key": "rules_link_2",
        "label": "Ссылка на политику",
        "hint": "",
        "type": "url",
        "group": "links",
    },
    {
        "key": "yookassa_stub_enabled",
        "label": "Демо-режим ЮKassa",
        "hint": "Вкл — демо-оплата. Без ключей магазина демо всегда активно",
        "type": "bool",
        "group": "payments",
    },
]


async def get_setting_value(session: AsyncSession, key: str) -> str:
    result = await session.execute(select(AppSetting).where(AppSetting.key == key))
    row = result.scalar_one_or_none()
    if row is not None and row.value is not None and str(row.value).strip() != "":
        return str(row.value)
    return env_defaults().get(key, "")


async def get_setting_int(session: AsyncSession, key: str) -> int:
    return int(float(await get_setting_value(session, key)))


async def get_setting_float(session: AsyncSession, key: str) -> float:
    return float(await get_setting_value(session, key))


async def get_setting_bool(session: AsyncSession, key: str) -> bool:
    raw = (await get_setting_value(session, key)).strip().lower()
    return raw in ("1", "true", "yes", "on", "enabled")


async def get_all_settings(session: AsyncSession) -> dict[str, str]:
    result = await session.execute(select(AppSetting))
    data = {s.key: s.value for s in result.scalars().all()}
    defaults = env_defaults()
    for key, default in defaults.items():
        # Пустая строка в БД = fallback на .env
        if key not in data or data[key] is None or str(data[key]).strip() == "":
            data[key] = default
    return data


async def upsert_setting(session: AsyncSession, key: str, value: str) -> None:
    result = await session.execute(select(AppSetting).where(AppSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        session.add(AppSetting(key=key, value=value))
