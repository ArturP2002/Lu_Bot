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
from services.name_search import expand_name_variants, extract_names_from_query
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
    names: list[str] = field(default_factory=list)
    verified_only: bool = False
    prefer_viewer_city: bool = True
    require_match: bool = False


@dataclass
class EventFilters:
    city: str | None = None
    keywords: list[str] = field(default_factory=list)
    today_only: bool = False
    category: str | None = None
    prefer_viewer_city: bool = True
    require_match: bool = False


# Канонические категории БД + алиасы из живой речи
_EVENT_CATEGORY_ALIASES: list[tuple[tuple[str, ...], str]] = [
    (("на хату", "хату", "хата", "квартирник", "квартирн", "домашн"), "На хату"),
    (("праздник", "день рождения", "birthday", "юбилей", "свят"), "Праздники"),
    (("игр", "настол", "мафи", "board", "playstation", "приставк"), "Игры"),
    (("посидел", "чай", "кофе", "общен"), "Посиделки"),
]

# Синонимы тем: запрос «кино» должен ловить title/description с «фильм»
_EVENT_TOPIC_SYNONYMS: dict[str, tuple[str, ...]] = {
    "кино": ("кино", "фильм", "cinema", "movie", "кинотеатр", "сериал"),
    "спорт": ("спорт", "футбол", "йога", "трениров", "fitness", "зал", "бег", "воркаут"),
    "бар": ("бар", "паб", "коктейл", "пивн"),
    "клуб": ("клуб", "дискотек", "рейв", "танцпол", "ночн"),
    "концерт": ("концерт", "музык", "гитар", "джаз", "live"),
    "пикник": ("пикник", "шашлык", "мангал", "парк"),
    "йога": ("йога", "медитац", "стретч"),
    "настолк": ("настол", "мафи", "uno"),
}


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
    names = extract_names_from_query(query)
    keywords = _extract_keywords(query)
    # убрать из keywords токены города и имени
    name_stems = {stem for n in names for stem in expand_name_variants(n)}
    if city:
        city_parts = {p.lower() for p in re.findall(r"[а-яёa-z\-]+", city, re.I)}
        keywords = [k for k in keywords if k not in city_parts and not any(k in p or p in k for p in city_parts)]
    if names:
        keywords = [
            k
            for k in keywords
            if k not in name_stems
            and not any(k.startswith(s[:4]) or s.startswith(k[:4]) for s in name_stems if len(k) >= 3)
        ]

    prefer_viewer = not any_city and not city
    return PeopleFilters(
        city=None if any_city else city,
        gender=gender,
        age_min=age_min,
        age_max=age_max,
        keywords=keywords,
        names=names,
        verified_only="вериф" in q or "проверен" in q,
        prefer_viewer_city=prefer_viewer,
        require_match=bool(names),
    )


def _detect_event_category(query_lower: str) -> str | None:
    """Каноническое имя категории из запроса, если тема узнаваема."""
    for aliases, canonical in _EVENT_CATEGORY_ALIASES:
        if any(a in query_lower for a in aliases):
            return canonical
    return None


def expand_event_topic_tokens(*parts: str | None) -> list[str]:
    """Варианты для жёсткого матча: категория + keywords + синонимы."""
    out: list[str] = []
    seen: set[str] = set()

    def _add(token: str) -> None:
        t = token.lower().strip()
        if len(t) < 2 or t in seen:
            return
        seen.add(t)
        out.append(t)

    for part in parts:
        if not part:
            continue
        raw = part.lower().strip()
        _add(raw)
        for syn_key, syns in _EVENT_TOPIC_SYNONYMS.items():
            if raw == syn_key or raw.startswith(syn_key) or syn_key.startswith(raw):
                for s in syns:
                    _add(s)
            elif any(raw.startswith(s) or s.startswith(raw) for s in syns if len(s) >= 3):
                for s in syns:
                    _add(s)
                _add(syn_key)
        for aliases, canonical in _EVENT_CATEGORY_ALIASES:
            can_l = canonical.lower()
            if raw == can_l or any(raw.startswith(a) or a.startswith(raw) for a in aliases if len(a) >= 3):
                _add(can_l)
                for a in aliases:
                    _add(a)
    return out[:16]


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

    category = _detect_event_category(q)
    # Тема из свободных слов (кино/бар/…), если категории ещё нет
    if not category:
        for topic, syns in _EVENT_TOPIC_SYNONYMS.items():
            if topic in q or any(len(s) >= 4 and s in q for s in syns):
                if topic not in keywords:
                    keywords.insert(0, topic)
                break

    if category:
        cat_tokens = set(expand_event_topic_tokens(category))
        keywords = [
            k
            for k in keywords
            if k not in cat_tokens
            and not any(
                (len(k) >= 3 and len(t) >= 3 and (k.startswith(t[:4]) or t.startswith(k[:4])))
                for t in cat_tokens
            )
        ]

    prefer_viewer = (near or not city) and not any_city
    has_topic = bool(keywords) or bool(category)
    return EventFilters(
        city=None if any_city else (viewer.city if near and viewer.city and not city else city),
        keywords=keywords,
        today_only=today,
        category=category,
        prefer_viewer_city=prefer_viewer,
        require_match=has_topic,
    )


async def _ai_parse_filters(query: str, viewer: User, kind: str) -> dict | None:
    """LLM → JSON-фильтры для поиска по БД."""
    if not settings.openai_api_key:
        return None
    schema_people = (
        '{"city": string|null, "gender": "male"|"female"|null, '
        '"age_min": int|null, "age_max": int|null, '
        '"names": string[], "keywords": string[], '
        '"verified_only": bool, "any_city": bool}'
    )
    schema_events = (
        '{"city": string|null, "keywords": string[], "today_only": bool, '
        '"category": "На хату"|"Праздники"|"Игры"|"Посиделки"|string|null, '
        '"any_city": bool}'
    )
    schema = schema_people if kind == "people" else schema_events
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        if kind == "people":
            extra_hint = (
                "names — личные имена людей из запроса (Ксюша, Диана, Саша); "
                "keywords — только интересы/тема (йога, спорт), без имён и стоп-слов. "
            )
        else:
            extra_hint = (
                "category — канон: «На хату», «Праздники», «Игры», «Посиделки» если тема ясна; "
                "keywords — тема/место/атмосфера (кино, бар, шашлык, квартирник), без стоп-слов. "
            )
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"Извлеки параметры поиска {('людей' if kind == 'people' else 'тусовок')} "
                        f"из запроса пользователя в JSON по схеме: {schema}. "
                        f"Город пользователя по умолчанию: {viewer.city or 'неизвестен'}. "
                        f"{extra_hint}"
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
    names_raw = data.get("names") if isinstance(data.get("names"), list) else base.names
    names = [str(n).lower().strip() for n in (names_raw or []) if str(n).strip() and not _is_stopword(str(n))]
    if not names:
        names = list(base.names)
    keywords = data.get("keywords") if isinstance(data.get("keywords"), list) else base.keywords
    keywords = [str(k).lower().strip() for k in keywords if str(k).strip() and not _is_stopword(str(k))]
    name_stems = {stem for n in names for stem in expand_name_variants(n)}
    keywords = [k for k in keywords if k not in name_stems]
    return PeopleFilters(
        city=str(city).strip() if city else None,
        gender=gender,
        age_min=int(data["age_min"]) if data.get("age_min") else base.age_min,
        age_max=int(data["age_max"]) if data.get("age_max") else base.age_max,
        keywords=keywords[:6],
        names=names[:4],
        verified_only=bool(data.get("verified_only")) or base.verified_only,
        prefer_viewer_city=not any_city and not city,
        require_match=bool(names) or base.require_match,
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
    raw_cat = data.get("category")
    category = str(raw_cat).strip() if raw_cat else None
    if category:
        detected = _detect_event_category(category.lower())
        if detected:
            category = detected
    else:
        category = base.category
    if not keywords:
        keywords = list(base.keywords)
    if category:
        cat_tokens = set(expand_event_topic_tokens(category))
        keywords = [
            k
            for k in keywords
            if k not in cat_tokens
            and not any(
                (len(k) >= 3 and len(t) >= 3 and (k.startswith(t[:4]) or t.startswith(k[:4])))
                for t in cat_tokens
            )
        ]
    has_topic = bool(keywords) or bool(category)
    return EventFilters(
        city=str(city).strip() if city else None,
        keywords=keywords[:6],
        today_only=bool(data.get("today_only")) or base.today_only,
        category=category,
        prefer_viewer_city=not any_city and not city,
        require_match=has_topic or base.require_match,
    )


def _name_match_clause(variants: list[str]):
    """WHERE: display_name / bio / username содержит хотя бы один вариант имени."""
    parts = []
    for v in variants:
        like = f"%{v}%"
        parts.append(User.display_name.ilike(like))
        parts.append(User.bio.ilike(like))
        parts.append(User.username.ilike(like))
    return or_(*parts) if parts else None


def _event_topic_match_clause(tokens: list[str]):
    """WHERE: title / description / category / address содержит хотя бы один токен темы."""
    parts = []
    for t in tokens:
        like = f"%{t}%"
        parts.append(Event.title.ilike(like))
        parts.append(Event.description.ilike(like))
        parts.append(Event.category.ilike(like))
        parts.append(Event.address.ilike(like))
    return or_(*parts) if parts else None


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

    name_variants: list[str] = []
    for n in f.names:
        for v in expand_name_variants(n):
            if v not in name_variants:
                name_variants.append(v)

    city = f.city or (viewer.city if f.prefer_viewer_city else None)
    require_name = bool(f.names) or f.require_match

    from config import get_settings
    from services.app_settings_service import get_setting_bool
    from services.geo_service import has_coords, sql_haversine_km

    settings = get_settings()
    geo_enabled = await get_setting_bool(session, "geo_search_enabled")
    use_geo = geo_enabled and has_coords(viewer) and (f.prefer_viewer_city or not f.city)

    async def _run(*, apply_city: bool, apply_keywords: bool, apply_names: bool) -> list[User]:
        clauses = list(base)
        score = User.rating_avg * 10
        if apply_names and name_variants:
            name_clause = _name_match_clause(name_variants)
            if name_clause is not None:
                clauses.append(name_clause)
            for v in name_variants:
                like = f"%{v}%"
                score = score + case(
                    (User.display_name.ilike(like), 40),
                    (User.username.ilike(like), 20),
                    (User.bio.ilike(like), 15),
                    else_=0,
                )
        if apply_city and use_geo and not f.city:
            # Ранжирование по близости (без жёсткого фильтра, кроме явного города в запросе)
            dist = sql_haversine_km(User.latitude, User.longitude, viewer.latitude, viewer.longitude)
            score = score + case(
                (User.latitude.is_(None), 0),
                (dist < settings.geo_same_city_km, 50),
                (dist < settings.geo_nearby_radius_km, 25),
                else_=0,
            )
        elif apply_city and city:
            exact, soft = _city_match_clause(User.city, city)
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

    # Поиск по имени: жёсткий фильтр, без fallback на «топ города»
    if require_name and name_variants:
        rows = await _run(apply_city=True, apply_keywords=True, apply_names=True)
        if not rows and (f.city or f.prefer_viewer_city):
            rows = await _run(apply_city=False, apply_keywords=True, apply_names=True)
        return rows

    rows = await _run(apply_city=True, apply_keywords=True, apply_names=False)
    if not rows and f.keywords:
        # Интересы: ослабить город, но не отдавать случайных людей без keywords
        rows = await _run(apply_city=False, apply_keywords=True, apply_names=False)
    if not rows and not f.keywords:
        rows = await _run(apply_city=True, apply_keywords=False, apply_names=False)
        if not rows:
            rows = await _run(apply_city=False, apply_keywords=False, apply_names=False)
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
    """Поиск тусовок по БД: жёсткий матч темы + релевантный score (не лента pin/boost)."""
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
    topic_tokens = expand_event_topic_tokens(f.category, *f.keywords)
    require_topic = bool(f.require_match) or bool(topic_tokens)

    from config import get_settings
    from services.app_settings_service import get_setting_bool
    from services.geo_service import geo_bbox_clauses, has_coords, sql_haversine_km

    settings = get_settings()
    geo_enabled = await get_setting_bool(session, "geo_search_enabled")
    use_geo = geo_enabled and has_coords(viewer) and f.prefer_viewer_city and not f.city

    async def _run(*, apply_city: bool, apply_topic: bool) -> list[Event]:
        clauses = list(base)
        # Релевантность темы важнее pin/boost — иначе всегда «лента по порядку»
        score = case((Event.pinned_until.is_not(None), 8), else_=0) + case(
            (Event.boosted_at.is_not(None), 4), else_=0
        )
        if apply_city and use_geo:
            radius = settings.geo_nearby_radius_km
            clauses.extend(
                geo_bbox_clauses(
                    Event.latitude, Event.longitude, viewer.latitude, viewer.longitude, radius
                )
            )
            dist = sql_haversine_km(
                Event.latitude, Event.longitude, viewer.latitude, viewer.longitude
            )
            clauses.append(dist <= radius)
            score = score + case(
                (dist < settings.geo_same_city_km, 50),
                (dist < radius, 25),
                else_=0,
            )
        elif apply_city and city:
            exact, soft = _city_match_clause(Event.city, city)
            if f.city:
                clauses.append(or_(exact, soft))
            score = score + case((exact, 50), (soft, 25), else_=0)
        if apply_topic and topic_tokens:
            topic_clause = _event_topic_match_clause(topic_tokens)
            if topic_clause is not None:
                clauses.append(topic_clause)
            for t in topic_tokens:
                like = f"%{t}%"
                score = score + case(
                    (Event.title.ilike(like), 45),
                    (Event.category.ilike(like), 35),
                    (Event.description.ilike(like), 22),
                    (Event.address.ilike(like), 12),
                    else_=0,
                )
        result = await session.execute(
            select(Event)
            .where(and_(*clauses))
            .order_by(score.desc(), Event.boosted_at.desc().nullslast(), Event.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # Тема из запроса: жёсткий фильтр, без fallback на «топ закреплённых»
    if require_topic and topic_tokens:
        rows = await _run(apply_city=True, apply_topic=True)
        if not rows and (f.city or f.prefer_viewer_city):
            rows = await _run(apply_city=False, apply_topic=True)
        return rows

    rows = await _run(apply_city=True, apply_topic=False)
    if not rows and (f.city or f.prefer_viewer_city):
        rows = await _run(apply_city=False, apply_topic=False)
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


def _people_db_context(
    users: list[User],
    *,
    names: list[str] | None = None,
    keywords: list[str] | None = None,
) -> str:
    if not users:
        if names:
            shown = ", ".join(names)
            return (
                f"По имени не найдено: {shown}. "
                "В базе нет анкет с таким именем (учти уменьшительные и полное имя). "
                "Не предлагай других людей вместо запрошенного имени."
            )
        if keywords:
            return (
                f"По интересам ({', '.join(keywords)}) никого не найдено. "
                "Не выдумывай анкеты."
            )
        return "Никого не найдено в БД. Не выдумывай людей."
    match = "name" if names else ("keyword" if keywords else "ranked")
    lines = [f"Результаты поиска (match={match}, count={len(users)}):"]
    for u in users:
        lines.append(
            f"id={u.id}; имя={u.display_name}; username={u.username or '—'}; "
            f"возраст={u.age}; город={u.city}; пол={u.gender}; "
            f"верифицирован={u.verified}; рейтинг={u.rating_avg}; "
            f"bio={(u.bio or '')[:160]}"
        )
    return "\n".join(lines)


def _events_db_context(
    events: list[Event],
    *,
    keywords: list[str] | None = None,
    category: str | None = None,
) -> str:
    topic_bits = [*(keywords or [])]
    if category:
        topic_bits.insert(0, category)
    if not events:
        if topic_bits:
            shown = ", ".join(topic_bits)
            return (
                f"По теме не найдено: {shown}. "
                "В базе нет активных тусовок с такой тематикой. "
                "Не предлагай другие мероприятия вместо запрошенной темы."
            )
        return "Тусовок не найдено в БД. Не выдумывай мероприятия."
    match = "topic" if topic_bits else "ranked"
    lines = [f"Результаты поиска тусовок (match={match}, count={len(events)}):"]
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
            "description": (
                "Поиск анкет людей в БД LUMA. "
                "Для поиска по имени передай names (Ксюша, Диана). "
                "keywords — только интересы/тема, не имена."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Город или пусто"},
                    "gender": {"type": "string", "enum": ["male", "female"]},
                    "age_min": {"type": "integer"},
                    "age_max": {"type": "integer"},
                    "names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Личные имена из запроса",
                    },
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Интересы/тема без имён",
                    },
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
            "description": (
                "Поиск активных тусовок в БД LUMA по теме/категории/городу. "
                "keywords — тема (кино, бар, шашлык); "
                "category — «На хату», «Праздники», «Игры», «Посиделки»."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Город или пусто"},
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Тема/атмосфера тусовки",
                    },
                    "today_only": {"type": "boolean"},
                    "category": {
                        "type": "string",
                        "description": "Каноническая категория или свободная тема",
                    },
                    "any_city": {"type": "boolean"},
                },
            },
        },
    },
]

async def _run_tool(session: AsyncSession, viewer: User, name: str, args: dict) -> str:
    if name == "search_people_db":
        from services.name_search import DIMINUTIVE_TO_CANON, stem_name

        any_city = bool(args.get("any_city"))
        city = None if any_city else args.get("city")
        names = [str(k) for k in (args.get("names") or []) if str(k).strip()][:4]
        keywords = [str(k) for k in (args.get("keywords") or []) if str(k).strip()][:6]

        def _looks_like_name(token: str) -> bool:
            key = token.lower().replace("ё", "е")
            st = stem_name(key)
            return (
                key in DIMINUTIVE_TO_CANON
                or st in DIMINUTIVE_TO_CANON
                or (st + "а") in DIMINUTIVE_TO_CANON
                or (st + "я") in DIMINUTIVE_TO_CANON
            )

        if not names and keywords:
            moved = [k for k in keywords if _looks_like_name(k)]
            if moved:
                names = moved
                keywords = [k for k in keywords if k not in moved]

        f = PeopleFilters(
            city=str(city).strip() if city else None,
            gender=args.get("gender") if args.get("gender") in ("male", "female") else None,
            age_min=args.get("age_min"),
            age_max=args.get("age_max"),
            keywords=keywords,
            names=names,
            verified_only=bool(args.get("verified_only")),
            prefer_viewer_city=not any_city and not city,
            require_match=bool(names),
        )
        users = await search_people(session, viewer, "", limit=12, filters=f)
        return _people_db_context(users, names=names or None, keywords=keywords or None)
    if name == "search_events_db":
        any_city = bool(args.get("any_city"))
        city = None if any_city else args.get("city")
        keywords = [str(k) for k in (args.get("keywords") or []) if str(k).strip()][:6]
        raw_cat = args.get("category")
        category = str(raw_cat).strip() if raw_cat else None
        if category:
            detected = _detect_event_category(category.lower())
            if detected:
                category = detected
            elif not keywords:
                # свободная тема из category → keywords
                keywords = [category.lower()]
                category = None
        has_topic = bool(keywords) or bool(category)
        f = EventFilters(
            city=str(city).strip() if city else None,
            keywords=keywords,
            today_only=bool(args.get("today_only")),
            category=category,
            prefer_viewer_city=not any_city and not city,
            require_match=has_topic,
        )
        events = await search_events(session, viewer, "", limit=12, filters=f)
        return _events_db_context(events, keywords=keywords or None, category=category)
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
            f"Я LU (демо-режим без OPENAI_API_KEY).\n\n"
            f"{_format_people(people, user)}\n\n{_format_events(events, user)}"
        )

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    system = (
        "Ты LU — спокойный премиальный консьерж бота знакомств и мероприятий. "
        "Говори уверенно, коротко и по делу: 2–5 предложений, без канцелярита и без "
        "шаблонов вроде «Конечно! Я помогу…». Без нумерованных списков без нужды. "
        "Для любых вопросов про людей или тусовки СНАЧАЛА вызови инструменты "
        "search_people_db / search_events_db — они ходят в реальную БД. "
        f"Город пользователя: {user.city or 'неизвестен'}. "
        "Опирайся только на данные инструментов. Не выдумывай имена, возраст, города, тусовки. "
        "Если искали человека по имени и БД пуста — честно скажи, что не нашла, "
        "и предложи одно уточнение (город или полное имя). "
        "Не подменяй запрошенное имя другими людьми из выдачи. "
        "Если искали тусовку по теме и БД пуста — честно скажи, что таких нет, "
        "и предложи уточнить тему или город. Не подменяй тему другими мероприятиями. "
        "При находках людей кратко: имя, возраст, город и одна деталь из bio. "
        "При находках тусовок: название, город, дата/время и одна деталь. "
        "Отвечай на языке пользователя."
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
            max_tokens=800,
            temperature=0.5,
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

BLOCK_CATEGORIES = ("porn", "drugs", "qr", "ads", "fraud", "nude", "violence", "hate", "minors")

TEXT_MODERATION_PROMPT = (
    "Ты модератор описания анкеты dating/тусовки бота. "
    "Запрещены: порно и интим-услуги/эскорт, наркотики, мошенничество, "
    "навязчивая реклама и промо каналов/ссылок, QR/скам-приглашения, "
    "оружие и призывы к насилию, разжигание ненависти, "
    "любой контент с несовершеннолетними, поиск секса за деньги. "
    "Обычное описание хобби, знакомств и тусовок — разрешено. "
    'Ответь строго JSON: {"ok": true/false, "reason": "краткая категория на русском или пусто"}'
)

PHOTO_MODERATION_PROMPT = (
    "Ты модератор фото анкеты dating-бота. Смотри картинку внимательно.\n\n"
    "РАЗРЕШЕНО (это НЕ нагота):\n"
    "• Бельё, трусы, лифчик, бра, топ, спортивный топ, купальник, бикини — даже если открыт живот/бёдра\n"
    "• Частично открытая одежда, кроп-топ, прозрачная ткань поверх белья\n"
    "• Мужской голый торс / грудь без майки — всегда ok\n"
    "• Обычные портреты и повседневные фото\n\n"
    "ЗАПРЕЩЕНО:\n"
    "• Видны гениталии\n"
    "• Женская грудь БЕЗ ткани: видны соски или ареолы (не прикрыты бельём/топом/руками/волосами)\n"
    "• Явная порнография, наркотики, QR-коды, реклама/мошенничество\n\n"
    "ПРАВИЛО: если на груди женщины лежит любая ткань (лифчик, бра, купальник, топ) — "
    "female_bare_nipples=false и ok=true, даже если много кожи.\n"
    "Не путай бельё/купальник с «полной наготой».\n\n"
    "Ответь строго JSON:\n"
    '{"has_genitalia": bool, "female_bare_nipples": bool, '
    '"covered_by_underwear_or_swimwear": bool, "has_qr": bool, '
    '"other_forbidden": bool, "ok": bool, "reason": "кратко на русском или пусто"}'
)


def _decide_photo_moderation(data: dict) -> tuple[bool, str]:
    """Итоговый вердикт по структурированному ответу vision-модели."""
    has_genitalia = bool(data.get("has_genitalia"))
    female_bare = bool(data.get("female_bare_nipples"))
    covered = bool(data.get("covered_by_underwear_or_swimwear"))
    has_qr = bool(data.get("has_qr"))
    other = bool(data.get("other_forbidden"))
    reason = str(data.get("reason") or "").strip()

    # Бельё/купальник перекрывает ложные срабатывания «оголённая грудь»
    if covered and not has_genitalia and not has_qr and not other:
        return True, ""

    if has_genitalia:
        return False, reason or "полная нагота"
    if female_bare and not covered:
        return False, reason or "оголённая женская грудь"
    if has_qr:
        return False, reason or "QR-код"
    if other:
        return False, reason or "нарушение"

    # Fallback на поле ok, но смягчаем типичные ложные причины
    if data.get("ok", True):
        return True, ""
    soft = reason.lower()
    false_positive = any(
        s in soft
        for s in (
            "частично",
            "бель",
            "купальн",
            "бикини",
            "трус",
            "лифчик",
            "бюстгальтер",
            "открыт",
            "swimsuit",
            "lingerie",
            "underwear",
            "бра",
            "топ",
        )
    )
    hard = any(
        s in soft
        for s in ("генитал", "сосок", "ареол", "вагин", "пенис", "порно", "qr")
    )
    if false_positive and not hard:
        return True, ""
    return False, reason or "нарушение"


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
                {"role": "system", "content": TEXT_MODERATION_PROMPT},
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
                        {"type": "text", "text": PHOTO_MODERATION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        },
                    ],
                }
            ],
            max_tokens=120,
            temperature=0,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content or "{}")
        return _decide_photo_moderation(data)
    except Exception as e:
        logger.warning("moderate_photo failed: %s", e)
        return True, ""


async def moderate_telegram_photo(bot, file_id: str, caption: str | None = None) -> tuple[bool, str]:
    """Скачать фото из Telegram и прогнать через moderate_photo."""
    from io import BytesIO

    try:
        buf = BytesIO()
        await bot.download(file_id, destination=buf)
        file_bytes = buf.getvalue()
    except Exception as e:
        logger.warning("moderate_telegram_photo download failed: %s", e)
        return True, ""
    if not file_bytes:
        return True, ""
    return await moderate_photo(file_bytes=file_bytes, caption=caption)


async def moderate_video(caption: str | None = None) -> tuple[bool, str]:
    """Проверка видео по подписи/описанию (полный анализ видео — через caption)."""
    return await moderate_text(caption or "")
