"""Backfill координат по уникальным городам + regeocode одной сущности."""

from __future__ import annotations

import asyncio
import logging

from redis.asyncio import Redis
from sqlalchemy import func, select, update

from config import get_settings
from core.database import get_session_factory
from models import Event, User
from services.geo_service import GEO_SOURCE_BACKFILL, geocode_city

logger = logging.getLogger(__name__)
settings = get_settings()


async def backfill_user_event_geo(ctx=None, *, delay_sec: float = 0.35, limit_cities: int | None = None) -> dict:
    """Геокодировать уникальные города без координат у users/events."""
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    factory = get_session_factory()
    stats = {"cities": 0, "users_updated": 0, "events_updated": 0, "misses": 0}

    async with factory() as session:
        user_cities = await session.execute(
            select(func.lower(User.city))
            .where(
                User.city.is_not(None),
                User.city != "",
                User.latitude.is_(None),
            )
            .distinct()
        )
        event_cities = await session.execute(
            select(func.lower(Event.city))
            .where(
                Event.city.is_not(None),
                Event.city != "",
                Event.latitude.is_(None),
            )
            .distinct()
        )
        cities = sorted({*(r[0] for r in user_cities.all() if r[0]), *(r[0] for r in event_cities.all() if r[0])})
        if limit_cities is not None:
            cities = cities[:limit_cities]

        # Оригинальный регистр: берём первое вхождение
        display: dict[str, str] = {}
        for city_l in cities:
            row = await session.execute(
                select(User.city).where(func.lower(User.city) == city_l).limit(1)
            )
            name = row.scalar_one_or_none()
            if not name:
                row = await session.execute(
                    select(Event.city).where(func.lower(Event.city) == city_l).limit(1)
                )
                name = row.scalar_one_or_none()
            if name:
                display[city_l] = name

    try:
        for city_l, name in display.items():
            stats["cities"] += 1
            result = await geocode_city(name, redis)
            if not result:
                stats["misses"] += 1
                logger.info("backfill miss city=%s", name)
                await asyncio.sleep(delay_sec)
                continue

            async with factory() as session:
                ures = await session.execute(
                    update(User)
                    .where(
                        func.lower(User.city) == city_l,
                        User.latitude.is_(None),
                    )
                    .values(
                        city=result.city,
                        latitude=result.latitude,
                        longitude=result.longitude,
                        geo_source=GEO_SOURCE_BACKFILL,
                    )
                )
                eres = await session.execute(
                    update(Event)
                    .where(
                        func.lower(Event.city) == city_l,
                        Event.latitude.is_(None),
                    )
                    .values(
                        city=result.city,
                        latitude=result.latitude,
                        longitude=result.longitude,
                        geo_source=GEO_SOURCE_BACKFILL,
                    )
                )
                await session.commit()
                stats["users_updated"] += ures.rowcount or 0
                stats["events_updated"] += eres.rowcount or 0

            logger.info(
                "backfill city=%s -> %s users=%s events=%s",
                name,
                result.city,
                ures.rowcount,
                eres.rowcount,
            )
            await asyncio.sleep(delay_sec)
    finally:
        await redis.aclose()

    logger.info("backfill done %s", stats)
    return stats


async def regeocode_entity(ctx, entity_type: str, entity_id: int) -> bool:
    """Повторный forward-geocode одной сущности по сохранённому city."""
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    factory = get_session_factory()
    try:
        async with factory() as session:
            if entity_type == "user":
                obj = await session.get(User, entity_id)
            elif entity_type == "event":
                obj = await session.get(Event, entity_id)
            else:
                return False
            if not obj or not (obj.city or "").strip():
                return False
            if obj.latitude is not None and obj.longitude is not None:
                return True
            result = await geocode_city(obj.city, redis)
            if not result:
                return False
            obj.city = result.city
            obj.latitude = result.latitude
            obj.longitude = result.longitude
            obj.geo_source = GEO_SOURCE_BACKFILL
            await session.commit()
            return True
    finally:
        await redis.aclose()
