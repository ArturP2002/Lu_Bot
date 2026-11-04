"""Сервис мероприятий: фильтры, boost/pin, mass-invite, закрытие набора."""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models import Event, EventApplication, EventCategory, EventStatus, User
from models.entities import ApplicationStatus
from services.sparks_service import add_transaction
from services.user_service import is_premium
from bot.texts.i18n import lang_of
from bot.texts.ui_labels import tx
from services.geo_service import distance_suffix_for

settings = get_settings()

# Premium: закреп со скидкой 50%; поднятие в топ — бесплатно раз в час
PREMIUM_PIN_DISCOUNT = 0.50
FREE_BOOST_COOLDOWN = timedelta(hours=1)
MASS_INVITE_LIMIT = 30
MSK = ZoneInfo("Europe/Moscow")


def _add_one_calendar_month(dt: datetime) -> datetime:
    """01.01 → 01.02 (с учётом длины месяца)."""
    month = dt.month + 1
    year = dt.year
    if month > 12:
        month = 1
        year += 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(dt.day, last_day)
    return dt.replace(year=year, month=month, day=day)


def parse_event_datetime_parts(date_str: str, time_str: str | None = None) -> datetime | None:
    """Собрать aware datetime (МСК) из строк даты/времени тусовки."""
    date_raw = (date_str or "").strip()
    time_raw = (time_str or "19:00").strip() or "19:00"
    if not date_raw:
        return None
    date_formats = ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%y", "%d/%m/%y")
    time_formats = ("%H:%M", "%H.%M", "%H:%M:%S")
    parsed_date = None
    for fmt in date_formats:
        try:
            parsed_date = datetime.strptime(date_raw, fmt).date()
            break
        except ValueError:
            continue
    if parsed_date is None:
        return None
    parsed_time = None
    for fmt in time_formats:
        try:
            parsed_time = datetime.strptime(time_raw, fmt).time()
            break
        except ValueError:
            continue
    if parsed_time is None:
        return None
    return datetime.combine(parsed_date, parsed_time, tzinfo=MSK)


def parse_event_ends_at(event: Event) -> datetime | None:
    """Момент окончания тусовки (дата+время МСК) в UTC-aware datetime."""
    ends = parse_event_datetime_parts(event.event_date or "", event.event_time)
    return ends


def parse_user_event_datetime(text: str) -> tuple[str, str, datetime] | None:
    """Разобрать ввод пользователя «ДД.ММ.ГГГГ ЧЧ:ММ» → (date, time, ends_at_msk)."""
    raw = (text or "").strip()
    if not raw:
        return None
    parts = raw.split(maxsplit=1)
    date_s = parts[0]
    time_s = parts[1] if len(parts) > 1 else "19:00"
    ends = parse_event_datetime_parts(date_s, time_s)
    if ends is None:
        return None
    # Нормализуем сохраняемый формат
    return ends.strftime("%d.%m.%Y"), ends.strftime("%H:%M"), ends


def validate_event_schedule(ends_at: datetime, *, now: datetime | None = None) -> str | None:
    """None если ок, иначе ключ ошибки i18n.

    Максимум — календарный месяц вперёд (01.01 → весь день 01.02 включительно).
    """
    from datetime import time as dtime

    now = now or datetime.now(MSK)
    if now.tzinfo is None:
        now = now.replace(tzinfo=MSK)
    else:
        now = now.astimezone(MSK)
    ends = ends_at.astimezone(MSK) if ends_at.tzinfo else ends_at.replace(tzinfo=MSK)
    if ends <= now:
        return "EVENT_DATETIME_PAST"
    max_day = _add_one_calendar_month(now).date()
    max_end = datetime.combine(max_day, dtime(23, 59, 59), tzinfo=MSK)
    if ends > max_end:
        return "EVENT_DATETIME_TOO_FAR"
    return None


async def close_expired_events(session: AsyncSession, bot) -> int:
    """Закрыть active-тусовки, у которых дата+время уже прошли (МСК)."""
    result = await session.execute(select(Event).where(Event.status == EventStatus.ACTIVE.value))
    events = list(result.scalars().all())
    now = datetime.now(timezone.utc)
    closed = 0
    for event in events:
        ends = parse_event_ends_at(event)
        if ends is None:
            continue
        ends_utc = ends.astimezone(timezone.utc)
        if ends_utc > now:
            continue
        try:
            await close_event_and_invite(session, bot, event)
            closed += 1
        except Exception:
            import logging

            logging.getLogger(__name__).exception("auto-close event %s failed", event.id)
    return closed


async def get_boost_base_price(session: AsyncSession) -> int:
    from services.app_settings_service import get_setting_int

    return max(1, await get_setting_int(session, "event_boost_price"))


async def get_pin_base_price(session: AsyncSession) -> int:
    from services.app_settings_service import get_setting_int

    return max(1, await get_setting_int(session, "event_pin_price"))


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def premium_free_boost_available(event: Event) -> bool:
    """Можно ли поднять тусовку бесплатно (Premium, не чаще раза в час на событие)."""
    if not event.boosted_at:
        return True
    return datetime.now(timezone.utc) - _aware(event.boosted_at) >= FREE_BOOST_COOLDOWN


async def get_boost_price_for_user(
    session: AsyncSession,
    user: User,
    event: Event | None = None,
) -> int:
    """Цена поднятия: Premium — 0 раз в час, иначе полная цена из настроек."""
    base = await get_boost_base_price(session)
    if is_premium(user) and event is not None and premium_free_boost_available(event):
        return 0
    return base


async def get_pin_price_for_user(session: AsyncSession, user: User, hours: int = 1) -> int:
    """Цена закрепа: Premium — скидка 50%."""
    hours = max(1, min(hours, 24))
    base = await get_pin_base_price(session) * hours
    if is_premium(user):
        return max(1, int(base * (1 - PREMIUM_PIN_DISCOUNT)))
    return base


async def count_active_events(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count(Event.id)).where(
            Event.organizer_id == user_id,
            Event.status == EventStatus.ACTIVE.value,
        )
    )
    return result.scalar() or 0


async def count_successful_organized(session: AsyncSession, user_id: int) -> int:
    """Тусовки, которые состоялись: набор закрыт и есть принятые участники."""
    result = await session.execute(
        select(func.count(Event.id)).where(
            Event.organizer_id == user_id,
            Event.status == EventStatus.CLOSED.value,
            (Event.men_count + Event.women_count) > 0,
        )
    )
    return int(result.scalar() or 0)


async def sync_events_organized(session: AsyncSession, user: User) -> int:
    """Обновить счётчик «организовал» по фактически состоявшимся тусовкам."""
    count = await count_successful_organized(session, user.id)
    if user.events_organized != count:
        user.events_organized = count
    return count


async def can_create_event(session: AsyncSession, user) -> tuple[bool, str]:
    count = await count_active_events(session, user.id)
    limit = 3 if is_premium(user) else 1
    if count >= limit:
        return False, f"Достигнут лимит активных мероприятий ({limit})"
    return True, ""


async def boost_event(session: AsyncSession, user: User, event: Event) -> int:
    if event.organizer_id != user.id:
        raise ValueError("Только организатор может поднять тусовку")
    if event.status != EventStatus.ACTIVE.value:
        raise ValueError("Тусовка не активна")
    price = await get_boost_price_for_user(session, user, event)
    if price > 0:
        if user.sparks_balance < price:
            raise ValueError("Недостаточно Искр")
        await add_transaction(session, user.id, -price, "event_boost", event.id)
    event.boosted_at = datetime.now(timezone.utc)
    return price


async def pin_event(session: AsyncSession, user: User, event: Event, hours: int = 1) -> int:
    if event.organizer_id != user.id:
        raise ValueError("Только организатор может закрепить тусовку")
    if event.status != EventStatus.ACTIVE.value:
        raise ValueError("Тусовка не активна")
    hours = max(1, min(hours, 24))
    price = await get_pin_price_for_user(session, user, hours=hours)
    if user.sparks_balance < price:
        raise ValueError("Недостаточно Искр")
    await add_transaction(session, user.id, -price, "event_pin", event.id)
    now = datetime.now(timezone.utc)
    base = event.pinned_until if event.pinned_until and _aware(event.pinned_until) > now else now
    event.pinned_until = _aware(base) + timedelta(hours=hours)
    return price


async def find_events(
    session: AsyncSession,
    viewer: User,
    *,
    category_id: int | None = None,
    exclude_id: int | None = None,
    limit: int = 20,
    redis=None,
) -> list[Event]:
    """Лента тусовок с фильтрами категорий и сортировкой pin/boost.

    filter_type:
      - time (Сегодня) — по дате события «сегодня» (МСК) и/или тегу категории
      - geo (Рядом) — по расстоянию (если geo_search_enabled) или тот же город
      - all (Все тусовки) — все активные без фильтра тематики
      - type — тематика (На хату, Игры, Гулять, …) по полю Event.category
    """
    from services.app_settings_service import get_setting_bool
    from services.geo_service import (
        ensure_event_geo,
        ensure_user_geo,
        geo_bbox_clauses,
        has_coords,
        hydrate_missing_event_geo,
        sql_distance_order,
        sql_haversine_km,
    )

    now = datetime.now(ZoneInfo("Europe/Moscow"))
    today_variants = _today_date_variants(now)
    clauses = [Event.status == EventStatus.ACTIVE.value]
    if exclude_id:
        clauses.append(Event.id != exclude_id)

    geo_mode = False
    geo_rank_by_distance = False
    if category_id:
        category = await session.get(EventCategory, category_id)
        if category:
            ft = (category.filter_type or "type").strip().lower()
            name_l = (category.name or "").strip().lower()
            is_geo = (
                ft == "geo"
                or name_l in {"рядом", "near"}
                or "рядом" in name_l
                or "near" in name_l
            )
            if is_geo:
                geo_mode = True
                geo_enabled = await get_setting_bool(session, "geo_search_enabled")
                await ensure_user_geo(viewer, redis)
                try:
                    await hydrate_missing_event_geo(session, redis, limit_cities=40)
                except Exception:
                    logger = __import__("logging").getLogger(__name__)
                    logger.exception("event geo hydrate failed")
                if geo_enabled and has_coords(viewer):
                    geo_rank_by_distance = True
                    radius = settings.geo_nearby_radius_km
                    # С coords в радиусе ИЛИ тот же город текстом (пока без coords после fail геокодера)
                    in_radius = and_(
                        *geo_bbox_clauses(
                            Event.latitude,
                            Event.longitude,
                            viewer.latitude,
                            viewer.longitude,
                            radius,
                        ),
                        sql_haversine_km(
                            Event.latitude, Event.longitude, viewer.latitude, viewer.longitude
                        )
                        <= radius,
                    )
                    city = (viewer.city or "").strip()
                    if city:
                        same_city = func.lower(Event.city) == city.lower()
                        clauses.append(or_(in_radius, same_city))
                    else:
                        clauses.append(in_radius)
                else:
                    clauses.extend(_geo_city_fallback_clauses(viewer))
            elif ft == "all" or name_l in {"все тусовки", "all"} or "все тусовки" in name_l:
                pass  # все активные
            else:
                clauses.extend(_category_filter_clauses(category, viewer, today_variants))

    order = []
    if geo_rank_by_distance:
        order.append(
            sql_distance_order(Event.latitude, Event.longitude, viewer.latitude, viewer.longitude)
        )
    order.extend(
        [
            case((Event.pinned_until > datetime.now(timezone.utc), 1), else_=0).desc(),
            Event.pinned_until.desc().nullslast(),
            Event.boosted_at.desc().nullslast(),
            Event.id.desc(),
        ]
    )

    stmt = select(Event).where(and_(*clauses)).order_by(*order).limit(limit)
    result = await session.execute(stmt)
    events = list(result.scalars().all())
    if geo_rank_by_distance:
        for ev in events:
            await ensure_event_geo(ev, redis)
    return events


def _today_date_variants(now: datetime | None = None) -> list[str]:
    """Возможные форматы «сегодня» для сравнения с Event.event_date."""
    now = now or datetime.now(ZoneInfo("Europe/Moscow"))
    return [
        now.strftime("%d.%m.%Y"),
        now.strftime("%d/%m/%Y"),
        now.strftime("%Y-%m-%d"),
        now.strftime("%d.%m.%y"),
        now.strftime("%d/%m/%y"),
    ]


def _geo_city_fallback_clauses(viewer: User) -> list:
    city = (viewer.city or "").strip()
    if city:
        return [func.lower(Event.city) == city.lower()]
    return [Event.id == -1]


def _category_filter_clauses(
    category: EventCategory,
    viewer: User,
    today_variants: list[str],
) -> list:
    """SQL-условия для категории поиска (не geo — geo обрабатывается в find_events)."""
    ft = (category.filter_type or "type").strip().lower()
    name = (category.name or "").strip()
    name_l = name.lower()
    emoji_label = f"{(category.emoji or '').strip()} {name}".strip()

    # Сегодня / time — дата «сегодня» или тусовка с этим тегом категории
    if ft == "time" or name_l in {"сегодня", "today"} or "сегодня" in name_l or "today" in name_l:
        return [
            or_(
                Event.event_date.in_(today_variants),
                Event.category.ilike(f"%{name}%"),
                Event.category.ilike("%сегодня%"),
                Event.category.ilike("%today%"),
            )
        ]

    # Рядом / geo — fallback (основной путь в find_events)
    if ft == "geo" or name_l in {"рядом", "near"} or "рядом" in name_l or "near" in name_l:
        return _geo_city_fallback_clauses(viewer)

    # Все тусовки — без фильтра тематики
    if ft == "all" or name_l in {"все тусовки", "all"} or "все тусовки" in name_l:
        return []

    # Тематика — гибкое совпадение по названию / emoji+название (+ legacy aliases)
    aliases = [name]
    if name_l == "гулять":
        aliases.extend(["Праздники", "праздники"])
    elif name_l == "все тусовки":
        aliases.extend(["Посиделки", "посиделки"])
    return [
        or_(
            *[Event.category == a for a in aliases],
            Event.category == emoji_label,
            *[Event.category.ilike(f"%{a}%") for a in aliases],
        )
    ]


def is_topic_category(category: EventCategory) -> bool:
    """Категория-тематика для создания тусовки (не умный фильтр Сегодня/Рядом/Все)."""
    ft = (category.filter_type or "type").strip().lower()
    name_l = (category.name or "").strip().lower()
    if ft in {"time", "geo", "all"}:
        return False
    if name_l in {"сегодня", "today", "рядом", "near", "все тусовки", "all"}:
        return False
    if "сегодня" in name_l or "рядом" in name_l or "все тусовки" in name_l:
        return False
    return True


async def get_next_event(
    session: AsyncSession,
    viewer: User,
    *,
    category_id: int | None = None,
    after_id: int | None = None,
    redis=None,
) -> Event | None:
    events = await find_events(
        session, viewer, category_id=category_id, exclude_id=after_id, limit=5, redis=redis
    )
    return events[0] if events else None


async def mass_invite_candidates(
    session: AsyncSession,
    event: Event,
    *,
    limit: int = MASS_INVITE_LIMIT,
) -> list[User]:
    """Подходящие пользователи рядом (coords или тот же город, завершённая анкета)."""
    from services.app_settings_service import get_setting_bool
    from services.geo_service import geo_bbox_clauses, has_coords, sql_haversine_km, sql_distance_order

    already = select(EventApplication.user_id).where(EventApplication.event_id == event.id)
    clauses = [
        User.profile_completed.is_(True),
        User.disabled.is_(False),
        User.is_banned.is_(False),
        User.id != event.organizer_id,
        User.id.notin_(already),
    ]
    order = [User.id.desc()]
    geo_enabled = await get_setting_bool(session, "geo_search_enabled")
    if geo_enabled and has_coords(event):
        radius = settings.geo_nearby_radius_km
        clauses.extend(
            geo_bbox_clauses(User.latitude, User.longitude, event.latitude, event.longitude, radius)
        )
        dist = sql_haversine_km(User.latitude, User.longitude, event.latitude, event.longitude)
        clauses.append(dist <= radius)
        order = [
            sql_distance_order(User.latitude, User.longitude, event.latitude, event.longitude),
            User.id.desc(),
        ]
    elif event.city:
        clauses.append(func.lower(User.city) == event.city.lower())
    # Гендерный баланс: если нужны парни/девушки
    gender_or = []
    if event.men_needed > event.men_count:
        gender_or.append(User.gender == "male")
    if event.women_needed > event.women_count:
        gender_or.append(User.gender == "female")
    if gender_or:
        clauses.append(or_(*gender_or))

    result = await session.execute(select(User).where(and_(*clauses)).order_by(*order).limit(limit))
    return list(result.scalars().all())


async def send_mass_invites(
    session: AsyncSession,
    bot,
    user: User,
    event: Event,
) -> int:
    if not is_premium(user):
        raise ValueError("Только для Premium")
    if event.organizer_id != user.id:
        raise ValueError("Только организатор")
    if event.mass_invites_used >= 5:
        raise ValueError("Лимит массовых приглашений исчерпан")

    candidates = await mass_invite_candidates(session, event)
    sent = 0
    link = f"https://t.me/{settings.bot_username}?start=event_{event.id}"
    for cand in candidates:
        text = tx(
            cand,
            "MASS_INVITE",
            title=event.title,
            city=event.city,
            distance=distance_suffix_for(cand, event, lang_of(cand)),
            address=event.address,
            date=event.event_date,
            time=event.event_time,
            link=link,
        )
        try:
            await bot.send_message(cand.telegram_id, text)
            sent += 1
        except Exception:
            continue
    event.mass_invites_used += 1
    return sent


async def close_event_and_invite(
    session: AsyncSession,
    bot,
    event: Event,
) -> str:
    """Закрыть набор, сформировать invite-ссылку и разослать участникам."""
    event.status = EventStatus.CLOSED.value
    invite_link = f"https://t.me/{settings.bot_username}?start=evgroup_{event.id}"
    # Сохраняем «ссылку» в group_chat_id как маркер (отрицательный id = pending group)
    if event.group_chat_id is None:
        event.group_chat_id = -event.id

    result = await session.execute(
        select(EventApplication).where(
            EventApplication.event_id == event.id,
            EventApplication.status == ApplicationStatus.ACCEPTED.value,
        )
    )
    apps = list(result.scalars().all())
    participants: list[User] = []
    for app in apps:
        u = await session.get(User, app.user_id)
        if u:
            participants.append(u)

    organizer = await session.get(User, event.organizer_id)
    lines = []
    for p in participants:
        if p.username:
            lines.append(f"@{p.username} — {p.display_name}")
        else:
            lines.append(f"{p.display_name} (tg://user?id={p.telegram_id})")
    roster = "\n".join(lines) if lines else "—"
    org_line = f"@{organizer.username}" if organizer and organizer.username else (organizer.display_name if organizer else "—")

    targets = list(participants)
    if organizer:
        targets.append(organizer)
    seen: set[int] = set()
    for u in targets:
        if u.id in seen:
            continue
        seen.add(u.id)
        body = tx(
            u,
            "EVENT_CLOSED_ROSTER",
            title=event.title,
            org=org_line,
            roster=roster,
            link=invite_link,
        )
        try:
            await bot.send_message(u.telegram_id, body)
        except Exception:
            pass
    return invite_link


# TZ filter names for seed
TZ_CATEGORIES = [
    ("Сегодня", "🔥", "time"),
    ("Рядом", "📍", "geo"),
    ("Игры", "🎮", "type"),
    ("На хату", "🏠", "type"),
    ("Гулять", "☀️", "type"),
    ("Все тусовки", "🎉", "all"),
]
