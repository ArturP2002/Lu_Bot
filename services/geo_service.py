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

YANDEX_GEOCODER_URL = "https://geocode-maps.yandex.ru/1.x/"

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
    # 2 * 6371 * asin(sqrt(...))
    rlat = func.radians(literal(lat))
    rlon = func.radians(literal(lon))
    rlat2 = func.radians(lat_col)
    rlon2 = func.radians(lon_col)
    dlat = rlat2 - rlat
    dlon = rlon2 - rlon
    a = func.pow(func.sin(dlat / 2), 2) + func.cos(rlat) * func.cos(rlat2) * func.pow(func.sin(dlon / 2), 2)
    return 2 * _EARTH_RADIUS_KM * func.asin(func.least(1.0, func.sqrt(a)))


def geo_bbox_clauses(lat_col, lon_col, lat: float, lon: float, radius_km: float) -> list:
    """WHERE-условия: есть coords + bbox."""
    d_lat, d_lon = bbox_delta_deg(lat, radius_km)
    return [
        lat_col.is_not(None),
        lon_col.is_not(None),
        lat_col.between(lat - d_lat, lat + d_lat),
        lon_col.between(lon - d_lon, lon + d_lon),
    ]


def sql_distance_order(lat_col, lon_col, lat: float, lon: float):
    """ORDER BY distance (NULL coords → конец)."""
    dist = case(
        (
            and_coords(lat_col, lon_col),
            sql_haversine_km(lat_col, lon_col, lat, lon),
        ),
        else_=literal(1e9),
    )
    return dist


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
    dist = sql_haversine_km(lat_col, lon_col, viewer_lat, viewer_lon)
    near = and_coords(lat_col, lon_col) & (dist < same_city_km)
    if viewer_city and viewer_city.strip():
        same_str = func.lower(city_col) == viewer_city.strip().lower()
        return case((or_(same_str, near), 1), else_=0)
    return case((near, 1), else_=0)


def _parse_yandex_feature(feature: dict) -> GeocodeResult | None:
    try:
        pos = feature["Geometry"]["Point"].split()
        lon, lat = float(pos[0]), float(pos[1])
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
        city = text.split(",")[0].strip() if text else ""
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

    params = {
        **params,
        "apikey": settings.yandex_geocoder_api_key.strip(),
        "format": "json",
        "lang": "ru_RU",
        "results": "5",
    }
    timeout = httpx.Timeout(settings.geo_http_timeout_sec)
    result: GeocodeResult | None = None
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(YANDEX_GEOCODER_URL, params=params)
            if resp.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                await asyncio.sleep(0.4 * (attempt + 1))
                continue
            resp.raise_for_status()
            payload = resp.json()
            members = (
                payload.get("response", {})
                .get("GeoObjectCollection", {})
                .get("featureMember", [])
            )
            features = [m.get("GeoObject") for m in members if m.get("GeoObject")]
            prefer = "geocode" in params  # forward
            result = _pick_best_feature(features, prefer_locality=prefer)
            break
        except Exception as e:
            last_err = e
            if attempt == 0:
                await asyncio.sleep(0.4)
                continue
            logger.warning("yandex geocode failed: %s", e)

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
                # короткий negative cache, чтобы не долбить API
                await redis.set(cache_key, json.dumps({"miss": True}), ex=min(ttl, 3600))
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
