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
        "premium_price": str(s.premium_price_1m or s.premium_price),
        "premium_price_1m": str(s.premium_price_1m or s.premium_price),
        "premium_price_3m": str(s.premium_price_3m),
        "premium_price_6m": str(s.premium_price_6m),
        "premium_price_12m": str(s.premium_price_12m),
        "rating_reset_price": str(s.rating_reset_price),
        "event_boost_price": str(s.event_boost_price),
        "event_pin_price": str(s.event_pin_price),
        "withdraw_min": str(s.withdraw_min),
        "withdraw_fee_rate": str(s.withdraw_fee_rate),
        "withdraw_fee_rate_premium": str(s.withdraw_fee_rate_premium),
        "support_fee_rate": str(s.support_fee_rate),
        "support_fee_rate_premium": str(s.support_fee_rate_premium),
        "rules_link_1": s.rules_link_1,
        "rules_link_2": s.rules_link_2,
        "yookassa_stub_enabled": "1",
        "feed_filter_seeking": "1",
        "feed_filter_visible_to": "0",
        "feed_filter_city": "0",
        "geo_search_enabled": "0",
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
        "key": "premium_price_1m",
        "label": "Premium 1 месяц (Искры)",
        "hint": "Стоимость подписки на 1 месяц",
        "type": "int",
        "group": "pricing",
    },
    {
        "key": "premium_price_3m",
        "label": "Premium 3 месяца (Искры)",
        "hint": "Стоимость подписки на 3 месяца",
        "type": "int",
        "group": "pricing",
    },
    {
        "key": "premium_price_6m",
        "label": "Premium 6 месяцев (Искры)",
        "hint": "Стоимость подписки на 6 месяцев",
        "type": "int",
        "group": "pricing",
    },
    {
        "key": "premium_price_12m",
        "label": "Premium 12 месяцев (Искры)",
        "hint": "Стоимость подписки на 12 месяцев",
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
        "key": "event_boost_price",
        "label": "Поднятие тусовки в топ (Искры)",
        "hint": "Базовая цена; Premium — бесплатно раз в час",
        "type": "int",
        "group": "pricing",
    },
    {
        "key": "event_pin_price",
        "label": "Закреп тусовки за час (Искры)",
        "hint": "Базовая цена за 1 час; Premium — скидка 50%",
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
        "hint": "Доля без Premium, например 0.15 = 15%",
        "type": "float",
        "group": "fees",
    },
    {
        "key": "withdraw_fee_rate_premium",
        "label": "Комиссия вывода Premium",
        "hint": "Доля для Premium, например 0.07 = 7%",
        "type": "float",
        "group": "fees",
    },
    {
        "key": "support_fee_rate",
        "label": "Комиссия поддержки цели",
        "hint": "Для пользователей без Premium, например 0.1 = 10%",
        "type": "float",
        "group": "fees",
    },
    {
        "key": "support_fee_rate_premium",
        "label": "Комиссия поддержки цели Premium",
        "hint": "Для Premium, например 0.02 = 2%",
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
        "label": "Фильтр по городу / рядом",
        "hint": "При геопоиске — только в радиусе nearby; иначе точный город",
        "type": "bool",
        "group": "feed",
    },
    {
        "key": "geo_search_enabled",
        "label": "Геопоиск по координатам",
        "hint": "Ранжирование анкет/тусовок по расстоянию (нужен Yandex Geocoder + backfill)",
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
    # premium_price_1m ← legacy premium_price
    if key == "premium_price_1m":
        legacy = await session.execute(select(AppSetting).where(AppSetting.key == "premium_price"))
        legacy_row = legacy.scalar_one_or_none()
        if legacy_row is not None and legacy_row.value is not None and str(legacy_row.value).strip() != "":
            return str(legacy_row.value)
    return env_defaults().get(key, "")


# Месяцы подписки Premium → ключ настройки и число дней
PREMIUM_PLANS: dict[int, tuple[str, int]] = {
    1: ("premium_price_1m", 30),
    3: ("premium_price_3m", 90),
    6: ("premium_price_6m", 180),
    12: ("premium_price_12m", 365),
}


async def get_premium_prices(session: AsyncSession) -> dict[int, int]:
    """Цены Premium по длительности в месяцах."""
    prices: dict[int, int] = {}
    for months, (key, _days) in PREMIUM_PLANS.items():
        prices[months] = await get_setting_int(session, key)
    return prices


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
    # Если premium_price_1m ещё не задан в БД — взять legacy premium_price
    one_m_row = await session.execute(select(AppSetting).where(AppSetting.key == "premium_price_1m"))
    if one_m_row.scalar_one_or_none() is None:
        legacy = await session.execute(select(AppSetting).where(AppSetting.key == "premium_price"))
        legacy_row = legacy.scalar_one_or_none()
        if legacy_row is not None and legacy_row.value is not None and str(legacy_row.value).strip() != "":
            data["premium_price_1m"] = str(legacy_row.value)
    return data


async def upsert_setting(session: AsyncSession, key: str, value: str) -> None:
    result = await session.execute(select(AppSetting).where(AppSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        session.add(AppSetting(key=key, value=value))
