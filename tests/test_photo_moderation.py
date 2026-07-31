"""Тесты вердикта модерации фото."""

from services.luma_ai_service import _decide_photo_moderation


def test_lingerie_covered_allowed():
    ok, reason = _decide_photo_moderation(
        {
            "has_genitalia": False,
            "female_bare_nipples": True,  # модель ошиблась
            "covered_by_underwear_or_swimwear": True,
            "has_qr": False,
            "other_forbidden": False,
            "ok": False,
            "reason": "Полная нагота: видна обнажённая женская грудь",
        }
    )
    assert ok is True
    assert reason == ""


def test_partial_clothing_soft_reason_allowed():
    ok, reason = _decide_photo_moderation(
        {
            "ok": False,
            "reason": "Частично обнажённая одежда",
            "has_genitalia": False,
            "female_bare_nipples": False,
            "covered_by_underwear_or_swimwear": False,
            "has_qr": False,
            "other_forbidden": False,
        }
    )
    assert ok is True


def test_bare_female_breast_blocked():
    ok, reason = _decide_photo_moderation(
        {
            "has_genitalia": False,
            "female_bare_nipples": True,
            "covered_by_underwear_or_swimwear": False,
            "has_qr": False,
            "other_forbidden": False,
            "ok": False,
            "reason": "оголённая женская грудь",
        }
    )
    assert ok is False
    assert "грудь" in reason.lower() or reason


def test_genitalia_blocked():
    ok, _ = _decide_photo_moderation(
        {
            "has_genitalia": True,
            "female_bare_nipples": False,
            "covered_by_underwear_or_swimwear": False,
            "has_qr": False,
            "other_forbidden": False,
            "ok": False,
            "reason": "полная нагота",
        }
    )
    assert ok is False


def test_male_torso_ok():
    ok, reason = _decide_photo_moderation(
        {
            "has_genitalia": False,
            "female_bare_nipples": False,
            "covered_by_underwear_or_swimwear": False,
            "has_qr": False,
            "other_forbidden": False,
            "ok": True,
            "reason": "",
        }
    )
    assert ok is True
    assert reason == ""
