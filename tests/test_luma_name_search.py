"""Тесты нормализации имён и фильтров поиска LUMA."""

from __future__ import annotations

from types import SimpleNamespace

from services.luma_ai_service import (
    PeopleFilters,
    _people_db_context,
    parse_people_filters_heuristic,
)
from services.name_search import expand_name_variants, extract_names_from_query, stem_name


def _viewer(**kwargs):
    defaults = {"id": 1, "city": "Москва"}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_stem_ksyusha_accusative():
    assert stem_name("ксюшу") == "ксюш"


def test_expand_ksyusha_includes_ksenia():
    variants = expand_name_variants("ксюшу")
    assert "ксения" in variants
    assert "ксюша" in variants or "ксюш" in variants


def test_expand_diana():
    variants = expand_name_variants("Диану")
    assert "диана" in variants


def test_extract_names_najdi_ksyushu():
    assert extract_names_from_query("найди Ксюшу") == ["ксюшу"]


def test_extract_names_single_token():
    assert extract_names_from_query("Ксения") == ["ксения"]


def test_extract_names_interest_not_name():
    assert extract_names_from_query("кто любит йогу") == []


def test_heuristic_name_search_require_match():
    viewer = _viewer()
    f = parse_people_filters_heuristic("найди Ксюшу", viewer)
    assert f.names
    assert f.require_match is True
    assert "ксюшу" in f.names or any("ксюш" in n for n in f.names)


def test_heuristic_yoga_keywords_no_name():
    viewer = _viewer()
    f = parse_people_filters_heuristic("кто любит йогу", viewer)
    assert not f.names
    assert f.require_match is False
    assert any("йог" in k for k in f.keywords)


def test_people_db_context_empty_name():
    text = _people_db_context([], names=["ксюша"])
    assert "По имени не найдено" in text
    assert "ксюша" in text
    assert "Не предлагай других людей" in text


def test_people_db_context_with_users():
    u = SimpleNamespace(
        id=10,
        display_name="Ксения",
        username="ksu",
        age=25,
        city="Москва",
        gender="female",
        verified=True,
        rating_avg=4.5,
        bio="люблю йогу",
    )
    text = _people_db_context([u], names=["ксюша"])
    assert "match=name" in text
    assert "Ксения" in text
