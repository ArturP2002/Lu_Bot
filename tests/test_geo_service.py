"""Тесты геосервиса: haversine, format, degrade без ключа."""

from __future__ import annotations

import asyncio
import json
import math

import pytest

from services.geo_service import (
    GeocodeResult,
    bbox_delta_deg,
    format_distance_km,
    geocode_city,
    haversine_km,
    normalize_city_key,
)


def test_haversine_same_point():
    assert haversine_km(55.75, 37.62, 55.75, 37.62) == pytest.approx(0.0, abs=1e-6)


def test_haversine_moscow_spb_order():
    km = haversine_km(55.7558, 37.6173, 59.9343, 30.3351)
    assert 600 < km < 750


def test_haversine_closer_wins():
    moscow = (55.7558, 37.6173)
    khimki = (55.8970, 37.4297)
    tver = (56.8587, 35.9176)
    assert haversine_km(*moscow, *khimki) < haversine_km(*moscow, *tver)


def test_format_distance():
    assert format_distance_km(None) == ""
    assert format_distance_km(0.4) == " · <1 км"
    assert format_distance_km(3.2) == " · 3 км"
    assert format_distance_km(12.6) == " · 13 км"


def test_bbox_delta():
    d_lat, d_lon = bbox_delta_deg(55.75, 100)
    assert d_lat == pytest.approx(100 / 111.0, rel=1e-3)
    assert d_lon > 0
    assert math.isfinite(d_lon)


def test_normalize_city_key():
    assert normalize_city_key("  Москва  ") == "москва"


def test_geocode_city_without_api_key(monkeypatch):
    from config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "yandex_geocoder_api_key", "")
    assert asyncio.run(geocode_city("Москва", redis=None)) is None


def test_geocode_city_uses_cache(monkeypatch):
    class FakeRedis:
        def __init__(self):
            self.store = {}

        async def get(self, key):
            return self.store.get(key)

        async def set(self, key, value, ex=None):
            self.store[key] = value

    redis = FakeRedis()
    redis.store["geo:yx:fwd:москва"] = json.dumps({"city": "Москва", "lat": 55.75, "lon": 37.62})

    from config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "yandex_geocoder_api_key", "test-key")

    result = asyncio.run(geocode_city("Москва", redis=redis))
    assert isinstance(result, GeocodeResult)
    assert result.city == "Москва"
    assert result.latitude == 55.75


def test_distance_suffix_for():
    from types import SimpleNamespace

    from services.geo_service import distance_suffix_for

    a = SimpleNamespace(latitude=55.75, longitude=37.62)
    b = SimpleNamespace(latitude=55.76, longitude=37.63)
    assert "км" in distance_suffix_for(a, b, "ru")
    c = SimpleNamespace(latitude=None, longitude=None)
    assert distance_suffix_for(a, c, "ru") == ""
