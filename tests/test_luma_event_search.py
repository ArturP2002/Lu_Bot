"""Тесты фильтров и контекста поиска тусовок LUMA."""

from __future__ import annotations

from types import SimpleNamespace

from services.luma_ai_service import (
    _events_db_context,
    expand_event_topic_tokens,
    parse_event_filters_heuristic,
)


def _viewer(**kwargs):
    defaults = {"id": 1, "city": "Москва"}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_heuristic_cinema_require_match():
    f = parse_event_filters_heuristic("найди кино в Москве", _viewer())
    assert f.require_match is True
    assert f.city and "моск" in f.city.lower()
    assert any("кино" in k for k in f.keywords)


def test_heuristic_na_hatu_category():
    f = parse_event_filters_heuristic("ищу тусовку на хату", _viewer())
    assert f.category == "На хату"
    assert f.require_match is True


def test_heuristic_games_category():
    f = parse_event_filters_heuristic("настольные игры вечером", _viewer())
    assert f.category == "Игры"
    assert f.require_match is True


def test_heuristic_browse_no_topic():
    f = parse_event_filters_heuristic("найди тусовки рядом", _viewer())
    assert f.require_match is False
    assert not f.keywords
    assert f.category is None
    assert f.prefer_viewer_city is True


def test_expand_cinema_includes_film():
    tokens = expand_event_topic_tokens("кино")
    assert "кино" in tokens
    assert "фильм" in tokens


def test_expand_category_na_hatu():
    tokens = expand_event_topic_tokens("На хату")
    assert any("хат" in t for t in tokens)
    assert any("квартир" in t for t in tokens)


def test_events_db_context_empty_topic():
    text = _events_db_context([], keywords=["кино"], category=None)
    assert "По теме не найдено" in text
    assert "кино" in text
    assert "Не предлагай другие мероприятия" in text


def test_events_db_context_with_events():
    e = SimpleNamespace(
        id=7,
        title="Киноночь",
        city="Москва",
        event_date="06.08.2026",
        event_time="20:00",
        address="Арбат",
        category="Посиделки",
        price=0,
        men_count=1,
        women_count=2,
        men_needed=3,
        women_needed=3,
        description="смотрим фильм",
    )
    text = _events_db_context([e], keywords=["кино"])
    assert "match=topic" in text
    assert "Киноночь" in text
