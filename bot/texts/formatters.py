"""Форматирование карточек пользователей."""

from __future__ import annotations

from models import User
from services.user_service import is_premium
from bot.texts.i18n import lang_of, normalize_lang
from bot.texts.ui_labels import tx


def years_label(age: int | None, lang_or_user="ru") -> str:
    """Склонение возраста под язык UI."""
    if age is None:
        return "—"
    lang = normalize_lang(lang_or_user if isinstance(lang_or_user, str) else lang_of(lang_or_user))
    n = abs(int(age)) % 100
    if lang == "kk":
        word = tx(lang, "YEARS_MANY")
    elif 11 <= n <= 14:
        word = tx(lang, "YEARS_MANY")
    else:
        last = n % 10
        if last == 1:
            word = tx(lang, "YEARS_ONE")
        elif last in (2, 3, 4):
            word = tx(lang, "YEARS_FEW")
        else:
            word = tx(lang, "YEARS_MANY")
    return f"{age} {word}"


def _attr_label(prefix: str, code: str | None, lang: str) -> str:
    if not code:
        return "—"
    return tx(lang, f"{prefix}_{code}") or "—"


def format_own_profile(user: User, lang_or_user=None) -> str:
    """Формат карточки своего профиля."""
    lang = normalize_lang(
        lang_or_user
        if isinstance(lang_or_user, str)
        else lang_of(lang_or_user or user)
    )
    goal = user.goal
    goal_text = tx(lang, "PROFILE_GOAL_OWN", title=goal.title) if goal else "—"
    premium = " ⭐" if is_premium(user) else ""
    verified = " ✅" if user.verified else ""

    return tx(
        lang,
        "PROFILE_OWN",
        name=user.display_name,
        age=years_label(user.age, lang),
        premium=premium,
        verified=verified,
        bio=user.bio or "",
        sparks=user.sparks_balance,
        rating=user.rating_avg,
        rated=user.rating_count,
        attended=user.events_attended,
        organized=user.events_organized,
        goal=goal_text,
        gender=_attr_label("GENDER", user.gender, lang),
        seeking=_attr_label("SEEKING", user.seeking, lang),
        visible=_attr_label("VISIBLE", user.visible_to, lang),
        city=user.city or "—",
    )


def format_other_profile(user: User, lang_or_user="ru") -> str:
    """Формат карточки чужой анкеты."""
    lang = normalize_lang(lang_or_user if isinstance(lang_or_user, str) else lang_of(lang_or_user))
    goal = user.goal
    if goal and goal.target_sparks:
        remaining = max(0, goal.target_sparks - goal.collected_sparks)
        percent = int(100 * goal.collected_sparks / goal.target_sparks)
        goal_text = tx(
            lang,
            "PROFILE_GOAL_OTHER",
            title=goal.title,
            collected=goal.collected_sparks,
            target=goal.target_sparks,
            remaining=remaining,
            percent=min(100, percent),
        )
    else:
        goal_text = "—"
    badges = ""
    if is_premium(user):
        badges += " ⭐"
    if user.verified:
        badges += " ✅"

    return tx(
        lang,
        "PROFILE_OTHER",
        name=user.display_name,
        age=years_label(user.age, lang),
        badges=badges,
        bio=user.bio or "",
        rating=user.rating_avg,
        rated=user.rating_count,
        attended=user.events_attended,
        organized=user.events_organized,
        goal=goal_text,
        city=user.city or "—",
    )
