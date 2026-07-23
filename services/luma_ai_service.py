"""AI-помощник LUMA: поиск людей/тусовок по БД + модерация контента."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI
from redis.asyncio import Redis
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models import Event, EventStatus, User
from services.user_service import is_premium

logger = logging.getLogger(__name__)
settings = get_settings()

STOPWORDS = {
    "найди", "найти", "поиск", "поищи", "покажи", "хочу", "ищу", "ищем",
    "человек", "человека", "людей", "люди", "кто", "кого", "мне", "для",
    "девушку", "парня", "девушки", "парни", "женщину", "мужчину", "женщины", "мужчины",
    "город", "города", "городе", "года", "лет", "возраст", "есть", "тут",
    "рядом", "около", "пожалуйста", "можешь", "можно", "нужно", "надо", "какой",
    "какая", "какие", "этот", "эта", "эти", "там", "сюда", "или", "либо",
    "тусов", "тусовка", "тусовки", "тусовку", "тусовок", "мероприят", "мероприятие",
    "мероприятия", "встреча", "встречи", "вечерин", "вечеринка", "вечеринки", "party",
    "ивент", "ивенты", "событие", "события", "все", "весь", "вся", "всех", "любой",
    "любая", "любые", "где", "когда", "что", "как", "про", "просьба", "помощ",
    "помощник", "luma", "лума", "бот", "анкет", "анкета", "анкеты", "профиль",
    "сегодня", "завтра", "вечером", "днем", "утром", "ночью", "сейчас", "скоро",
    "интересн", "интересные", "интересный", "хорош", "хорошие", "новый", "новые",
    "свободн", "открыт", "активн", "любит", "люблю", "нравится", "хочет",
}

GENDER_MALE = ("парн", "мужчин", "парень", "мужчина", "хлопц", "паца", "boys", "guys", "male")
GENDER_FEMALE = ("девуш", "женщин", "девоч", "дівч", "қыз", "girl", "women", "female", "леди")
NEAR_WORDS = ("рядом", "около", "мой город", "в моём городе", "в моем городе", "поруч", "жақын", "near")
ANY_CITY_WORDS = ("везде", "любой город", "в другом", "других городах", "без города", "все города")


@dataclass
class PeopleFilters:
    city: str | None = None
    gender: str | None = None
    age_min: int | None = None
    age_max: int | None = None
    keywords: list[str] = field(default_factory=list)
    verified_only: bool = False
    prefer_viewer_city: bool = True


@dataclass
class EventFilters:
    city: str | None = None
    keywords: list[str] = field(default_factory=list)
    today_only: bool = False
    category: str | None = None
    prefer_viewer_city: bool = True


async def get_ai_daily_limit(session: AsyncSession) -> int:
    from services.app_settings_service import get_setting_int

    return await get_setting_int(session, "ai_daily_limit")


async def check_ai_limit(redis: Redis, user_id: int, limit: int) -> tuple[bool, int]:
    from datetime import date

    key = f"ai_requests:{user_id}:{date.today().isoformat()}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 86400)
    return count <= limit, count


def _normalize_word(w: str) -> str:
    return w.lower().strip("-")


def _is_stopword(w: str) -> bool:
    w = _normalize_word(w)
    if len(w) < 3:
        return True
    if w in STOPWORDS:
        return True
    return any(w.startswith(s) or s.startswith(w) for s in STOPWORDS if len(s) >= 4)


COMPOUND_CITY_FIRST = {
    "санкт", "нижний", "ростов", "усть", "набережные", "комсомольск", "петропавловск",
}
COMPOUND_CITY_SECOND = {
    "петербург", "петербурге", "петербурга", "новгород", "новгороде", "новгорода",
    "дону", "доне", "каме", "илиме", "амуре", "камчатский", "камчатском",
}


def _extract_city_from_query(query: str) -> str | None:
    q = query.strip()
    m = re.search(
        r"(?:^|[\s,])(?:в|во|из|город[еа]?|місто|қала)\s+([а-яёa-z\-]{3,})(?:\s+([а-яёa-z\-]{2,}))?",
        q,
        re.I,
    )
    if not m:
        return None
    first = m.group(1).strip("-")
    second = (m.group(2) or "").strip("-")
    if _is_stopword(first) or any(first.lower().startswith(g[:4]) for g in GENDER_MALE + GENDER_FEMALE):
        return None
    first_l = first.lower()
    if second:
        second_l = second.lower()
        if (
            first_l in COMPOUND_CITY_FIRST
            or second_l in COMPOUND_CITY_SECOND
            or "-" in first
        ) and not _is_stopword(second):
            return f"{first} {second}"
    return first


def _extract_keywords(query: str, *, min_len: int = 3, limit: int = 5) -> list[str]:
    words = re.findall(r"[а-яёa-z][а-яёa-z0-9\-]{2,}", query.lower(), re.I)
    out: list[str] = []
    for w in words:
        w = _normalize_word(w)
        if any(ch.isdigit() for ch in w):
            continue
        if _is_stopword(w):
            continue
        if any(w.startswith(g) or g.startswith(w) for g in GENDER_MALE + GENDER_FEMALE):
            continue
        if w not in out:
            out.append(w)
        if len(out) >= limit:
            break
    return out


def _city_search_token(city: str) -> str:
    """Укорачивает падежные окончания, чтобы «Москве» находило «Москва»."""
    c = city.lower().strip()
    for suf in (
        "ского", "скому", "ским", "ском", "ская", "ское",
        "ого", "ому", "ыми", "ами", "ях", "ах",
        "ом", "ем", "ой", "ей", "ию", "ии", "ие", "ия",
        "ая", "ое", "ые", "ых", "ую", "ый", "ий",
        "а", "у", "е", "ы", "и", "я", "ю",
    ):
        if len(c) > len(suf) + 3 and c.endswith(suf):
            c = c[: -len(suf)]
            break
    return c if len(c) >= 3 else city.lower().strip()


def _city_match_clause(column, city: str):
    token = _city_search_token(city)
    exact = func.lower(column) == city.lower().strip()
    soft = func.lower(column).ilike(f"%{token}%")
    return exact, soft


def _extract_age(query: str) -> tuple[int | None, int | None]:
    q = query.lower()
    m = re.search(r"(\d{2})\s*[-–—]\s*(\d{2})", q)
    if m:
        a1, a2 = int(m.group(1)), int(m.group(2))
        return min(a1, a2), max(a1, a2)
    m = re.search(r"(?:от|с)\s*(\d{2})", q)
    age_min = int(m.group(1)) if m else None
    m = re.search(r"(?:до|по)\s*(\d{2})", q)
    age_max = int(m.group(1)) if m else None
    m = re.search(r"(\d{2})\s*(?:лет|года|год)", q)
    if m and age_min is None and age_max is None:
        age = int(m.group(1))
        return max(18, age - 2), age + 2
    return age_min, age_max


def _extract_gender(query: str) -> str | None:
    q = query.lower()
    male = any(w in q for w in GENDER_MALE)
    female = any(w in q for w in GENDER_FEMALE)
    if male and not female:
        return "male"
    if female and not male:
        return "female"
    return None


def parse_people_filters_heuristic(query: str, viewer: User) -> PeopleFilters:
    q = query.lower().strip()
    city = _extract_city_from_query(query)
    any_city = any(w in q for w in ANY_CITY_WORDS)
    age_min, age_max = _extract_age(q)
    gender = _extract_gender(q)
    keywords = _extract_keywords(query)
    # убрать из keywords токены города
    if city:
        city_parts = {p.lower() for p in re.findall(r"[а-яёa-z\-]+", city, re.I)}
        keywords = [k for k in keywords if k not in city_parts and not any(k in p or p in k for p in city_parts)]

    prefer_viewer = not any_city and not city
    return PeopleFilters(
        city=None if any_city else city,
        gender=gender,
        age_min=age_min,
        age_max=age_max,
        keywords=keywords,
        verified_only="вериф" in q or "проверен" in q,
        prefer_viewer_city=prefer_viewer,
    )


def parse_event_filters_heuristic(query: str, viewer: User) -> EventFilters:
    q = query.lower().strip()
    city = _extract_city_from_query(query)
    any_city = any(w in q for w in ANY_CITY_WORDS)
    near = any(w in q for w in NEAR_WORDS)
    today = any(w in q for w in ("сегодня", "today", "бүгін", "сьогодні"))
    keywords = _extract_keywords(query, min_len=3, limit=6)
    if city:
        city_parts = {p.lower() for p in re.findall(r"[а-яёa-z\-]+", city, re.I)}
        keywords = [k for k in keywords if k not in city_parts]

    category = None
    for cat in ("на хату", "праздник", "игр", "посидел", "кино", "спорт", "бар", "клуб"):
        if cat in q:
            category = cat
            break

    prefer_viewer = (near or not city) and not any_city
    return EventFilters(
        city=None if any_city else (viewer.city if near and viewer.city and not city else city),
        keywords=keywords,
        today_only=today,
        category=category,
        prefer_viewer_city=prefer_viewer,
    )


async def _ai_parse_filters(query: str, viewer: User, kind: str) -> dict | None:
    """LLM → JSON-фильтры для поиска по БД."""
    if not settings.openai_api_key:
        return None
    schema_people = (
        '{"city": string|null, "gender": "male"|"female"|null, '
        '"age_min": int|null, "age_max": int|null, '
        '"keywords": string[], "verified_only": bool, "any_city": bool}'
    )
    schema_events = (
        '{"city": string|null, "keywords": string[], "today_only": bool, '
        '"category": string|null, "any_city": bool}'
    )
    schema = schema_people if kind == "people" else schema_events
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"Извлеки параметры поиска {('людей' if kind == 'people' else 'тусовок')} "
                        f"из запроса пользователя в JSON по схеме: {schema}. "
                        f"Город пользователя по умолчанию: {viewer.city or 'неизвестен'}. "
                        "keywords — только смысловые слова интересов/темы (без стоп-слов вроде "
                        "«найди», «тусовка», «люди»). Если город не указан явно — city=null. "
                        "any_city=true если просят искать везде."
                    ),
                },
                {"role": "user", "content": query[:500]},
            ],
            max_tokens=200,
            response_format={"type": "json_object"},
            temperature=0,
        )
        return json.loads(response.choices[0].message.content or "{}")
    except Exception as e:
        logger.warning("AI parse filters failed: %s", e)
        return None


async def resolve_people_filters(session: AsyncSession, viewer: User, query: str) -> PeopleFilters:
    base = parse_people_filters_heuristic(query, viewer)
    data = await _ai_parse_filters(query, viewer, "people")
    if not data:
        return base
    any_city = bool(data.get("any_city"))
    city = None if any_city else (data.get("city") or base.city)
    gender = data.get("gender") if data.get("gender") in ("male", "female") else base.gender
    keywords = data.get("keywords") if isinstance(data.get("keywords"), list) else base.keywords
    keywords = [str(k).lower().strip() for k in keywords if str(k).strip() and not _is_stopword(str(k))]
    return PeopleFilters(
        city=str(city).strip() if city else None,
        gender=gender,
        age_min=int(data["age_min"]) if data.get("age_min") else base.age_min,
        age_max=int(data["age_max"]) if data.get("age_max") else base.age_max,
        keywords=keywords[:6],
        verified_only=bool(data.get("verified_only")) or base.verified_only,
        prefer_viewer_city=not any_city and not city,
    )


async def resolve_event_filters(session: AsyncSession, viewer: User, query: str) -> EventFilters:
    base = parse_event_filters_heuristic(query, viewer)
    data = await _ai_parse_filters(query, viewer, "events")
    if not data:
        return base
    any_city = bool(data.get("any_city"))
    city = None if any_city else (data.get("city") or base.city)
    keywords = data.get("keywords") if isinstance(data.get("keywords"), list) else base.keywords
    keywords = [str(k).lower().strip() for k in keywords if str(k).strip() and not _is_stopword(str(k))]
    return EventFilters(
        city=str(city).strip() if city else None,
        keywords=keywords[:6],
        today_only=bool(data.get("today_only")) or base.today_only,
        category=(str(data["category"]).strip() if data.get("category") else base.category),
        prefer_viewer_city=not any_city and not city,
    )


async def search_people(
    session: AsyncSession,
    viewer: User,
    query: str,
    limit: int = 10,
    *,
    filters: PeopleFilters | None = None,
    use_ai_parse: bool = False,
) -> list[User]:
    """Поиск людей по БД: жёсткие фильтры + мягкий ранжирующий score."""
    f = filters
    if f is None:
        f = await resolve_people_filters(session, viewer, query) if use_ai_parse else parse_people_filters_heuristic(query, viewer)

    base = [
        User.profile_completed.is_(True),
        User.disabled.is_(False),
        User.is_banned.is_(False),
        User.id != viewer.id,
    ]
    if f.verified_only:
        base.append(User.verified.is_(True))
    if f.gender:
        base.append(User.gender == f.gender)
    if f.age_min is not None:
        base.append(User.age >= f.age_min)
    if f.age_max is not None:
        base.append(User.age <= f.age_max)

    city = f.city or (viewer.city if f.prefer_viewer_city else None)

    async def _run(apply_city: bool, apply_keywords: bool) -> list[User]:
        clauses = list(base)
        score = User.rating_avg * 10
        if apply_city and city:
            exact, soft = _city_match_clause(User.city, city)
            # если город явно в запросе — фильтруем; если только prefer — только boost
            if f.city:
                clauses.append(or_(exact, soft))
            score = score + case((exact, 50), (soft, 25), else_=0)
        if apply_keywords and f.keywords:
            for w in f.keywords:
                like = f"%{w}%"
                score = score + case(
                    (User.bio.ilike(like), 15),
                    (User.display_name.ilike(like), 8),
                    else_=0,
                )
        score = score + case((User.verified.is_(True), 5), else_=0)
        score = score + case((User.premium_until > datetime.now(timezone.utc), 25), else_=0)
        result = await session.execute(
            select(User).where(and_(*clauses)).order_by(score.desc(), User.id.desc()).limit(limit)
        )
        return list(result.scalars().all())

    rows = await _run(apply_city=True, apply_keywords=True)
    if not rows and f.keywords:
        rows = await _run(apply_city=True, apply_keywords=False)
    if not rows and (f.city or f.prefer_viewer_city):
        rows = await _run(apply_city=False, apply_keywords=bool(f.keywords))
    if not rows:
        rows = await _run(apply_city=False, apply_keywords=False)
    return rows


async def search_events(
    session: AsyncSession,
    viewer: User,
    query: str,
    limit: int = 10,
    *,
    filters: EventFilters | None = None,
    use_ai_parse: bool = False,
) -> list[Event]:
    """Поиск тусовок по БД с мягким ранжированием."""
    f = filters
    if f is None:
        f = await resolve_event_filters(session, viewer, query) if use_ai_parse else parse_event_filters_heuristic(query, viewer)

    today = datetime.now(ZoneInfo("Europe/Moscow"))
    today_variants = [
        today.strftime("%d.%m.%Y"),
        today.strftime("%d/%m/%Y"),
        today.strftime("%Y-%m-%d"),
        today.strftime("%d.%m.%y"),
    ]
    base = [Event.status == EventStatus.ACTIVE.value]
    if f.today_only:
        base.append(Event.event_date.in_(today_variants))

    city = f.city or (viewer.city if f.prefer_viewer_city else None)

    async def _run(apply_city: bool, apply_keywords: bool, apply_category: bool) -> list[Event]:
        clauses = list(base)
        score = case((Event.pinned_until.is_not(None), 40), else_=0) + case(
            (Event.boosted_at.is_not(None), 20), else_=0
        )
        if apply_city and city:
            exact, soft = _city_match_clause(Event.city, city)
            if f.city:
                clauses.append(or_(exact, soft))
            score = score + case((exact, 50), (soft, 25), else_=0)
        if apply_category and f.category:
            cat = f.category
            score = score + case(
                (Event.category.ilike(f"%{cat}%"), 30),
                (Event.title.ilike(f"%{cat}%"), 20),
                (Event.description.ilike(f"%{cat}%"), 10),
                else_=0,
            )
        if apply_keywords and f.keywords:
            for w in f.keywords:
                like = f"%{w}%"
                score = score + case(
                    (Event.title.ilike(like), 25),
                    (Event.category.ilike(like), 18),
                    (Event.description.ilike(like), 12),
                    (Event.address.ilike(like), 8),
                    (Event.city.ilike(like), 8),
                    else_=0,
                )
        result = await session.execute(
            select(Event)
            .where(and_(*clauses))
            .order_by(score.desc(), Event.boosted_at.desc().nullslast(), Event.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    rows = await _run(True, True, True)
    if not rows and f.keywords:
        rows = await _run(True, False, True)
    if not rows and (f.city or f.prefer_viewer_city):
        rows = await _run(False, True, True)
    if not rows:
        rows = await _run(False, False, False)
    return rows


def _format_people(users: list[User], lang_or_user="ru") -> str:
    from bot.texts.ui_labels import tx

    if not users:
        return tx(lang_or_user, "LUMA_PEOPLE_EMPTY")
    lines = [tx(lang_or_user, "LUMA_PEOPLE_FOUND")]
    for u in users:
        badge = " ✅" if u.verified else ""
        lines.append(f"• {u.display_name or 'Без имени'}, {u.age or '—'}, {u.city or '—'}{badge}")
        if u.bio:
            lines.append(f"  {u.bio[:120]}")
    return "\n".join(lines)


def _format_events(events: list[Event], lang_or_user="ru") -> str:
    from bot.texts.ui_labels import tx

    if not events:
        return tx(lang_or_user, "LUMA_EVENTS_EMPTY")
    lines = [tx(lang_or_user, "LUMA_EVENTS_FOUND")]
    for e in events:
        lines.append(
            tx(
                lang_or_user,
                "LUMA_EVENT_LINE",
                title=e.title,
                city=e.city,
                date=e.event_date,
                time=e.event_time,
                address=e.address,
                taken=e.men_count + e.women_count,
                need=e.men_needed + e.women_needed,
            )
        )
        if e.category:
            lines.append(f"  {e.category}")
        if e.description:
            lines.append(f"  {e.description[:100]}")
    return "\n".join(lines)


def _people_db_context(users: list[User]) -> str:
    if not users:
        return "Никого не найдено в БД."
    lines = []
    for u in users:
        lines.append(
            f"id={u.id}; имя={u.display_name}; возраст={u.age}; город={u.city}; "
            f"пол={u.gender}; верифицирован={u.verified}; рейтинг={u.rating_avg}; "
            f"bio={(u.bio or '')[:160]}"
        )
    return "\n".join(lines)


def _events_db_context(events: list[Event]) -> str:
    if not events:
        return "Тусовок не найдено в БД."
    lines = []
    for e in events:
        lines.append(
            f"id={e.id}; «{e.title}»; город={e.city}; дата={e.event_date} {e.event_time}; "
            f"адрес={e.address}; категория={e.category}; цена={e.price}; "
            f"места={e.men_count + e.women_count}/{e.men_needed + e.women_needed}; "
            f"описание={(e.description or '')[:120]}"
        )
    return "\n".join(lines)


_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_people_db",
            "description": "Поиск анкет людей в базе данных LUMA",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Город или пусто"},
                    "gender": {"type": "string", "enum": ["male", "female"]},
                    "age_min": {"type": "integer"},
                    "age_max": {"type": "integer"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "verified_only": {"type": "boolean"},
                    "any_city": {"type": "boolean"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_events_db",
            "description": "Поиск активных тусовок/мероприятий в базе данных LUMA",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Город или пусто"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "today_only": {"type": "boolean"},
                    "category": {"type": "string"},
                    "any_city": {"type": "boolean"},
                },
            },
        },
    },
]


async def _run_tool(session: AsyncSession, viewer: User, name: str, args: dict) -> str:
    if name == "search_people_db":
        any_city = bool(args.get("any_city"))
        city = None if any_city else args.get("city")
        f = PeopleFilters(
            city=str(city).strip() if city else None,
            gender=args.get("gender") if args.get("gender") in ("male", "female") else None,
            age_min=args.get("age_min"),
            age_max=args.get("age_max"),
            keywords=[str(k) for k in (args.get("keywords") or []) if str(k).strip()][:6],
            verified_only=bool(args.get("verified_only")),
            prefer_viewer_city=not any_city and not city,
        )
        users = await search_people(session, viewer, "", limit=12, filters=f)
        return _people_db_context(users)
    if name == "search_events_db":
        any_city = bool(args.get("any_city"))
        city = None if any_city else args.get("city")
        f = EventFilters(
            city=str(city).strip() if city else None,
            keywords=[str(k) for k in (args.get("keywords") or []) if str(k).strip()][:6],
            today_only=bool(args.get("today_only")),
            category=str(args["category"]).strip() if args.get("category") else None,
            prefer_viewer_city=not any_city and not city,
        )
        events = await search_events(session, viewer, "", limit=12, filters=f)
        return _events_db_context(events)
    return "Неизвестный инструмент"


async def ask_luma(session: AsyncSession, redis: Redis, user, message: str) -> str:
    """Ответ AI: tool-calling к поиску по БД или эвристический поиск."""
    if not is_premium(user):
        raise ValueError("Только для Premium")

    limit = await get_ai_daily_limit(session)
    ok, _count = await check_ai_limit(redis, user.id, limit)
    if not ok:
        raise ValueError("AI_LIMIT")

    if not settings.openai_api_key:
        people = await search_people(session, user, message, limit=8)
        events = await search_events(session, user, message, limit=8)
        return (
            f"Я LUMA (демо-режим без OPENAI_API_KEY).\n\n"
            f"{_format_people(people, user)}\n\n{_format_events(events, user)}"
        )

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    system = (
        "Ты LUMA — AI-помощник бота знакомств и мероприятий. "
        "Для любых вопросов про людей или тусовки СНАЧАЛА вызови инструменты "
        "search_people_db / search_events_db — они ходят в реальную БД. "
        f"Город пользователя: {user.city or 'неизвестен'}. "
        "Отвечай кратко на языке пользователя, опираясь только на данные из инструментов. "
        "Если БД пуста — честно скажи, что не нашла, и предложи уточнить запрос."
    )
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": message},
    ]

    for _ in range(3):
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=_TOOLS,
            tool_choice="auto",
            max_tokens=700,
        )
        choice = response.choices[0]
        msg = choice.message
        if msg.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = await _run_tool(session, user, tc.function.name, args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )
            continue

        if msg.content:
            return msg.content
        break

    # Фоллбек: прямой поиск по БД без GPT-ответа
    people = await search_people(session, user, message, limit=8, use_ai_parse=True)
    events = await search_events(session, user, message, limit=8, use_ai_parse=True)
    return f"{_format_people(people, user)}\n\n{_format_events(events, user)}"


# --- AI-модерация контента ---

BLOCK_CATEGORIES = ("porn", "drugs", "qr", "ads", "fraud")


async def moderate_text(text: str) -> tuple[bool, str]:
    """Проверка текста. True = ок, False = заблокировано + причина."""
    if not text or not text.strip():
        return True, ""

    lower = text.lower()
    drug_words = ("закладк", "мефедрон", "кокаин", "героин", "mdma", "амфетамин", "спайс")
    porn_words = ("onlyfans", "секс за", "интим услуг", "эскорт")
    fraud_words = ("гарант схем", "инвест сигнал", "100% доход", "развод на")
    if any(w in lower for w in drug_words):
        return False, "наркотики"
    if any(w in lower for w in porn_words):
        return False, "порно"
    if any(w in lower for w in fraud_words):
        return False, "мошенничество"
    if "t.me/" in lower and any(w in lower for w in ("подписывай", "канал", "реклама", "промокод")):
        return False, "реклама"

    if not settings.openai_api_key:
        return True, ""

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты модератор. Проверь текст на: porn, drugs, qr-codes (как приглашение к скаму), "
                        "ads (навязчивая реклама), fraud. Ответь JSON: "
                        '{"ok": true/false, "reason": "категория или пусто"}'
                    ),
                },
                {"role": "user", "content": text[:2000]},
            ],
            max_tokens=80,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        if data.get("ok", True):
            return True, ""
        return False, str(data.get("reason") or "нарушение")
    except Exception as e:
        logger.warning("moderate_text failed: %s", e)
        return True, ""


async def moderate_photo(file_bytes: bytes | None = None, caption: str | None = None) -> tuple[bool, str]:
    """Проверка фото (и подписи). Без байтов — только caption."""
    if caption:
        ok, reason = await moderate_text(caption)
        if not ok:
            return ok, reason
    if not file_bytes or not settings.openai_api_key:
        return True, ""
    try:
        import base64

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        b64 = base64.b64encode(file_bytes).decode()
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Проверь фото на порно, наркотики, QR-коды, рекламу, мошенничество. "
                                'JSON: {"ok": true/false, "reason": "..."}'
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        },
                    ],
                }
            ],
            max_tokens=80,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content or "{}")
        if data.get("ok", True):
            return True, ""
        return False, str(data.get("reason") or "нарушение")
    except Exception as e:
        logger.warning("moderate_photo failed: %s", e)
        return True, ""


async def moderate_video(caption: str | None = None) -> tuple[bool, str]:
    """Проверка видео по подписи/описанию (полный анализ видео — через caption)."""
    return await moderate_text(caption or "")
