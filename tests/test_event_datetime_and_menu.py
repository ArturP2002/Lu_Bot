"""Дата тусовки (+1 месяц), filter all, варианты меню Оценивать."""

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from bot.texts.ui_labels import all_menu_labels, resolve_menu_action
from services.event_service import (
    TZ_CATEGORIES,
    _category_filter_clauses,
    is_topic_category,
    parse_user_event_datetime,
    validate_event_schedule,
)
from services.like_inbox_service import LIKE_INBOX_THRESHOLD

MSK = ZoneInfo("Europe/Moscow")


def test_parse_and_month_limit():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=MSK)
    ok = parse_user_event_datetime("01.02.2026 19:00")
    assert ok is not None
    assert validate_event_schedule(ok[2], now=now) is None

    far = parse_user_event_datetime("02.02.2026 10:00")
    assert far is not None
    assert validate_event_schedule(far[2], now=now) == "EVENT_DATETIME_TOO_FAR"

    past = parse_user_event_datetime("01.01.2026 10:00")
    assert past is not None
    assert validate_event_schedule(past[2], now=now) == "EVENT_DATETIME_PAST"

    bad = parse_user_event_datetime("не дата")
    assert bad is None


def test_tz_categories_and_topic_filter():
    names = [c[0] for c in TZ_CATEGORIES]
    assert names == ["Сегодня", "Рядом", "Игры", "На хату", "Гулять", "Все тусовки"]
    assert ("Все тусовки", "🎉", "all") in TZ_CATEGORIES

    all_cat = SimpleNamespace(name="Все тусовки", emoji="🎉", filter_type="all")
    assert not is_topic_category(all_cat)
    assert _category_filter_clauses(all_cat, SimpleNamespace(city="Москва"), []) == []

    walk = SimpleNamespace(name="Гулять", emoji="☀️", filter_type="type")
    assert is_topic_category(walk)


def test_menu_rate_variants():
    from bot.texts.ui_labels import text_matches_menu_action

    labels = all_menu_labels("rate")
    assert any("Оценивать" in x for x in labels)
    for text in (
        "Оценивать❤️",
        "Оценивать❤",
        "Оценивать ❤️",
        "Оценивать",
        "Оценивать ❤️\u200b",
        "Оценивать❤️ ",
    ):
        assert resolve_menu_action(text) == "rate", text
        assert text_matches_menu_action(text, "rate"), text
    assert resolve_menu_action("Тусовки 🥳") == "events"
    assert resolve_menu_action("Лу 👩‍💼") == "luma"


def test_like_inbox_threshold():
    assert LIKE_INBOX_THRESHOLD == 3
