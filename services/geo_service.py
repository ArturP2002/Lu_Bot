"""Геокодинг (Yandex), расстояние и SQL-хелперы для поиска рядом."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from dataclasses import dataclass
from typing import Any

import httpx
from redis.asyncio import Redis
from sqlalchemy import case, func, literal, or_

from config import get_settings

logger = logging.getLogger(__name__)

GEO_SOURCE_LOCATION = "location"
GEO_SOURCE_CITY_CENTER = "city_center"
GEO_SOURCE_BACKFILL = "backfill"

YANDEX_GEOCODER_URL = "https://geocode-maps.yandex.ru/v1/"
# Старый endpoint (ключ от «JS API + Геокодер»); пробуем как fallback
YANDEX_GEOCODER_URL_LEGACY = "https://geocode-maps.yandex.ru/1.x/"

_EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class GeocodeResult:
    city: str
    latitude: float
    longitude: float


def has_coords(obj: Any) -> bool:
    lat = getattr(obj, "latitude", None)
    lon = getattr(obj, "longitude", None)
    return lat is not None and lon is not None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние между двумя точками в км."""
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def format_distance_km(km: float | None, lang: str = "ru") -> str:
    """Округлённая дистанция для UI. Пустая строка если нет данных."""
    if km is None or km < 0:
        return ""
    if km < 1:
        label = {"ru": "<1 км", "be": "<1 км", "uk": "<1 км", "kk": "<1 км"}.get(lang, "<1 км")
        return f" · {label}"
    rounded = int(round(km))
    unit = {"ru": "км", "be": "км", "uk": "км", "kk": "км"}.get(lang, "км")
    return f" · {rounded} {unit}"


def distance_suffix_for(viewer: Any, other: Any, lang: str = "ru") -> str:
    """Суффикс дистанции для карточки, если у обоих есть координаты."""
    if not has_coords(viewer) or not has_coords(other):
        return ""
    km = haversine_km(viewer.latitude, viewer.longitude, other.latitude, other.longitude)
    return format_distance_km(km, lang)


def bbox_delta_deg(lat: float, radius_km: float) -> tuple[float, float]:
    """Δlat / Δlon в градусах для bbox вокруг точки."""
    d_lat = radius_km / 111.0
    cos_lat = max(0.01, abs(math.cos(math.radians(lat))))
    d_lon = radius_km / (111.0 * cos_lat)
    return d_lat, d_lon


def normalize_city_key(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def sql_haversine_km(lat_col, lon_col, lat: float, lon: float):
    """SQL-выражение haversine (км) относительно точки (lat, lon)."""
    rlat = func.radians(literal(float(lat)))
    rlon = func.radians(literal(float(lon)))
    rlat2 = func.radians(lat_col)
    rlon2 = func.radians(lon_col)
    dlat = rlat2 - rlat
    dlon = rlon2 - rlon
    a = func.pow(func.sin(dlat / 2), 2) + func.cos(rlat) * func.cos(rlat2) * func.pow(func.sin(dlon / 2), 2)
    # clamp для asin: из‑за float a иногда чуть > 1
    a_clamped = func.least(literal(1.0), func.greatest(literal(0.0), a))
    return literal(2.0) * literal(_EARTH_RADIUS_KM) * func.asin(func.sqrt(a_clamped))


def geo_bbox_clauses(lat_col, lon_col, lat: float, lon: float, radius_km: float) -> list:
    """WHERE-условия: есть coords + bbox."""
    d_lat, d_lon = bbox_delta_deg(lat, radius_km)
    return [
        lat_col.is_not(None),
        lon_col.is_not(None),
        lat_col.between(lat - d_lat, lat + d_lat),
        lon_col.between(lon - d_lon, lon + d_lon),
    ]


def sql_distance_km_nullable(lat_col, lon_col, lat: float, lon: float):
    """Расстояние в км или NULL, если у кандидата нет координат."""
    return case(
        (and_coords(lat_col, lon_col), sql_haversine_km(lat_col, lon_col, lat, lon)),
        else_=None,
    )


def sql_distance_order(lat_col, lon_col, lat: float, lon: float):
    """ORDER BY distance: ближе выше, без coords — в конец."""
    return sql_distance_km_nullable(lat_col, lon_col, lat, lon).asc().nulls_last()


def and_coords(lat_col, lon_col):
    return lat_col.is_not(None) & lon_col.is_not(None)


def same_city_rank_expr(
    city_col,
    lat_col,
    lon_col,
    *,
    viewer_city: str | None,
    viewer_lat: float,
    viewer_lon: float,
    same_city_km: float,
):
    """1 = «свой город» (строка или близко), 0 = остальные."""
    dist = sql_distance_km_nullable(lat_col, lon_col, viewer_lat, viewer_lon)
    near = and_coords(lat_col, lon_col) & (dist < same_city_km)
    if viewer_city and viewer_city.strip():
        same_str = func.lower(func.coalesce(city_col, "")) == viewer_city.strip().lower()
        return case((or_(same_str, near), 1), else_=0)
    return case((near, 1), else_=0)


def _parse_point_pos(geometry: dict | None) -> tuple[float, float] | None:
    """Достать lon, lat из Geometry (форматы v1 и 1.x)."""
    if not geometry:
        return None
    point = geometry.get("Point")
    raw = None
    if isinstance(point, str):
        raw = point
    elif isinstance(point, dict):
        raw = point.get("pos") or point.get("coordinates")
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            try:
                return float(raw[0]), float(raw[1])
            except (TypeError, ValueError):
                return None
    # GeoJSON-подобный вариант
    coords = geometry.get("coordinates")
    if isinstance(coords, (list, tuple)) and len(coords) >= 2:
        try:
            return float(coords[0]), float(coords[1])
        except (TypeError, ValueError):
            return None
    if not raw or not isinstance(raw, str):
        return None
    parts = raw.replace(",", " ").split()
    if len(parts) < 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None


def _parse_yandex_feature(feature: dict) -> GeocodeResult | None:
    try:
        parsed_pos = _parse_point_pos(feature.get("Geometry") or {})
        if not parsed_pos:
            return None
        lon, lat = parsed_pos
    except (KeyError, IndexError, TypeError, ValueError):
        return None

    comps = (feature.get("metaDataProperty") or {}).get("GeocoderMetaData", {}).get("Address", {}).get(
        "Components"
    ) or []
    city = None
    for kind in ("locality", "area", "province", "district"):
        for c in comps:
            if c.get("kind") == kind and c.get("name"):
                city = str(c["name"]).strip()
                break
        if city:
            break
    if not city:
        # fallback: первая часть text до запятой
        text = (feature.get("metaDataProperty") or {}).get("GeocoderMetaData", {}).get("text") or ""
        # "Россия, Москва" → лучше последнее значимое / locality уже выше
        parts = [p.strip() for p in text.split(",") if p.strip()]
        city = parts[-1] if parts else ""
    if not city:
        return None
    return GeocodeResult(city=city[:255], latitude=lat, longitude=lon)


def _pick_best_feature(features: list[dict], *, prefer_locality: bool) -> GeocodeResult | None:
    if not features:
        return None
    if prefer_locality:
        for f in features:
            kind = (
                (f.get("metaDataProperty") or {})
                .get("GeocoderMetaData", {})
                .get("kind", "")
            )
            if kind in ("locality", "area", "province"):
                parsed = _parse_yandex_feature(f)
                if parsed:
                    return parsed
    return _parse_yandex_feature(features[0])


async def _yandex_request(params: dict, redis: Redis | None, cache_key: str, ttl: int) -> GeocodeResult | None:
    settings = get_settings()
    if not settings.yandex_geocoder_configured:
        logger.warning("yandex geocoder: API key not configured")
        return None

    if redis is not None:
        try:
            cached = await redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                if data.get("miss"):
                    return None
                return GeocodeResult(city=data["city"], latitude=data["lat"], longitude=data["lon"])
        except Exception as e:
            logger.warning("geo cache read failed: %s", e)

    req_params = {
        **params,
        "apikey": settings.yandex_geocoder_api_key.strip(),
        "format": "json",
        "lang": "ru_RU",
        "results": "5",
    }
    timeout = httpx.Timeout(settings.geo_http_timeout_sec)
    result: GeocodeResult | None = None
    last_err: Exception | None = None
    urls = (YANDEX_GEOCODER_URL, YANDEX_GEOCODER_URL_LEGACY)

    for url in urls:
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.get(url, params=req_params)
                if resp.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                    await asyncio.sleep(0.4 * (attempt + 1))
                    continue
                if resp.status_code >= 400:
                    logger.warning(
                        "yandex geocode HTTP %s url=%s body=%s",
                        resp.status_code,
                        url,
                        (resp.text or "")[:300],
                    )
                    last_err = RuntimeError(f"HTTP {resp.status_code}")
                    break  # следующий url
                payload = resp.json()
                members = (
                    payload.get("response", {})
                    .get("GeoObjectCollection", {})
                    .get("featureMember", [])
                )
                features = [m.get("GeoObject") for m in members if m.get("GeoObject")]
                prefer = bool(params.get("geocode")) and "kind" not in params
                result = _pick_best_feature(features, prefer_locality=prefer)
                if result:
                    last_err = None
                    break
                last_err = RuntimeError("empty geocode response")
                break
            except Exception as e:
                last_err = e
                if attempt == 0:
                    await asyncio.sleep(0.4)
                    continue
                logger.warning("yandex geocode failed url=%s: %s", url, e)
        if result:
            break

    if last_err and result is None:
        logger.info("geocode miss/fail key=%s err=%s", cache_key, last_err)

    if redis is not None:
        try:
            if result:
                await redis.set(
                    cache_key,
                    json.dumps({"city": result.city, "lat": result.latitude, "lon": result.longitude}),
                    ex=ttl,
                )
            else:
                # короткий negative cache (не на весь TTL — иначе после фикса ключа «Москва» мёртвая)
                await redis.set(cache_key, json.dumps({"miss": True}), ex=300)
        except Exception as e:
            logger.warning("geo cache write failed: %s", e)

    return result


async def geocode_city(name: str, redis: Redis | None = None) -> GeocodeResult | None:
    """Forward geocode: центр населённого пункта."""
    settings = get_settings()
    raw = (name or "").strip()
    if not raw:
        return None
    key = f"geo:yx:fwd:{normalize_city_key(raw)}"
    return await _yandex_request(
        {"geocode": raw},
        redis,
        key,
        settings.geo_cache_ttl_fwd_sec,
    )


async def reverse_geocode(lat: float, lon: float, redis: Redis | None = None) -> GeocodeResult | None:
    """Reverse geocode: название населённого пункта по координатам."""
    settings = get_settings()
    key = f"geo:yx:rev:{lat:.3f}:{lon:.3f}"
    # Для reverse сохраняем точные coords запроса в результате (не центр города)
    parsed = await _yandex_request(
        {"geocode": f"{lon},{lat}", "kind": "locality"},
        redis,
        key,
        settings.geo_cache_ttl_rev_sec,
    )
    if parsed:
        return GeocodeResult(city=parsed.city, latitude=lat, longitude=lon)
    # без kind=locality
    parsed = await _yandex_request(
        {"geocode": f"{lon},{lat}"},
        redis,
        f"{key}:any",
        settings.geo_cache_ttl_rev_sec,
    )
    if parsed:
        return GeocodeResult(city=parsed.city, latitude=lat, longitude=lon)
    return None


async def enqueue_regeocode(entity_type: str, entity_id: int) -> None:
    """Поставить задачу повторного геокодинга в arq (best-effort)."""
    settings = get_settings()
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        try:
            await pool.enqueue_job("regeocode_entity", entity_type, entity_id)
        finally:
            await pool.close()
    except Exception as e:
        logger.warning("enqueue regeocode failed %s/%s: %s", entity_type, entity_id, e)


def apply_geo_to_user(user, *, city: str, lat: float | None, lon: float | None, source: str | None) -> None:
    user.city = city[:255]
    user.latitude = lat
    user.longitude = lon
    user.geo_source = source


def apply_geo_to_event(event, *, city: str, lat: float | None, lon: float | None, source: str | None) -> None:
    event.city = city[:255]
    event.latitude = lat
    event.longitude = lon
    event.geo_source = source


async def ensure_user_geo(user, redis: Redis | None = None, *, persist: bool = True) -> bool:
    """Если нет coords, но есть city — проставить центр города. True если coords есть после вызова."""
    if has_coords(user):
        return True
    city = (getattr(user, "city", None) or "").strip()
    if not city:
        return False
    result = await geocode_city(city, redis)
    if not result:
        logger.warning("ensure_user_geo: geocode failed for city=%r user_id=%s", city, getattr(user, "id", None))
        return False
    user.latitude = result.latitude
    user.longitude = result.longitude
    user.geo_source = GEO_SOURCE_CITY_CENTER
    logger.info(
        "ensure_user_geo: user_id=%s city=%r -> %.5f,%.5f",
        getattr(user, "id", None),
        city,
        result.latitude,
        result.longitude,
    )
    return True


async def ensure_event_geo(event, redis: Redis | None = None, *, persist: bool = True) -> bool:
    """Если у тусовки нет coords — центр по Event.city."""
    if has_coords(event):
        return True
    city = (getattr(event, "city", None) or "").strip()
    if not city:
        return False
    result = await geocode_city(city, redis)
    if not result:
        logger.warning("ensure_event_geo: geocode failed for city=%r event_id=%s", city, getattr(event, "id", None))
        return False
    event.latitude = result.latitude
    event.longitude = result.longitude
    event.geo_source = GEO_SOURCE_CITY_CENTER
    return True


async def hydrate_missing_user_geo(
    session,
    redis: Redis | None = None,
    *,
    limit_cities: int = 40,
) -> int:
    """Проставить coords пользователям с city без lat/lon (уникальные города). Возвращает число городов."""
    from sqlalchemy import select, update

    from models import User

    result = await session.execute(
        select(func.lower(User.city))
        .where(
            User.city.is_not(None),
            User.city != "",
            User.latitude.is_(None),
            User.profile_completed.is_(True),
        )
        .distinct()
        .limit(limit_cities)
    )
    cities_l = [r[0] for r in result.all() if r[0]]
    filled = 0
    for city_l in cities_l:
        row = await session.execute(
            select(User.city).where(func.lower(User.city) == city_l).limit(1)
        )
        name = row.scalar_one_or_none()
        if not name:
            continue
        geo = await geocode_city(name, redis)
        if not geo:
            logger.warning("hydrate_missing_user_geo: miss city=%r", name)
            continue
        await session.execute(
            update(User)
            .where(func.lower(User.city) == city_l, User.latitude.is_(None))
            .values(
                latitude=geo.latitude,
                longitude=geo.longitude,
                geo_source=GEO_SOURCE_CITY_CENTER,
            )
        )
        filled += 1
        logger.info("hydrate_missing_user_geo: %r -> %.5f,%.5f", name, geo.latitude, geo.longitude)
        await asyncio.sleep(0.05)
    if filled:
        await session.flush()
    return filled


async def hydrate_missing_event_geo(
    session,
    redis: Redis | None = None,
    *,
    limit_cities: int = 40,
) -> int:
    """Проставить coords тусовкам с city без lat/lon."""
    from sqlalchemy import select, update

    from models import Event

    result = await session.execute(
        select(func.lower(Event.city))
        .where(
            Event.city.is_not(None),
            Event.city != "",
            Event.latitude.is_(None),
        )
        .distinct()
        .limit(limit_cities)
    )
    cities_l = [r[0] for r in result.all() if r[0]]
    filled = 0
    for city_l in cities_l:
        row = await session.execute(
            select(Event.city).where(func.lower(Event.city) == city_l).limit(1)
        )
        name = row.scalar_one_or_none()
        if not name:
            continue
        geo = await geocode_city(name, redis)
        if not geo:
            continue
        await session.execute(
            update(Event)
            .where(func.lower(Event.city) == city_l, Event.latitude.is_(None))
            .values(
                latitude=geo.latitude,
                longitude=geo.longitude,
                geo_source=GEO_SOURCE_CITY_CENTER,
            )
        )
        filled += 1
        await asyncio.sleep(0.05)
    if filled:
        await session.flush()
    return filled
