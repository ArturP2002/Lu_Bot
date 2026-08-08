"""Сервис ленты анкет."""

from datetime import datetime, timezone

from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_settings
from models import Like, ProfileSkip, Rating, User

settings = get_settings()


async def record_profile_skip(session: AsyncSession, from_user_id: int, to_user_id: int) -> bool:
    """Сохранить пропуск анкеты. True — запись создана."""
    if from_user_id == to_user_id:
        return False
    existing = await session.execute(
        select(ProfileSkip.id)
        .where(
            ProfileSkip.from_user_id == from_user_id,
            ProfileSkip.to_user_id == to_user_id,
        )
        .limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return False
    session.add(ProfileSkip(from_user_id=from_user_id, to_user_id=to_user_id))
    await session.flush()
    return True


async def get_next_profile(session: AsyncSession, viewer: User, exclude_ids: list[int] | None = None) -> User | None:
    """Получить следующую анкету для просмотра.

    Лайкнутые и пропущенные анкеты в ленту больше не попадают.
    Premium-анкеты чаще в топе: активный Premium выше остальных.
    При geo_search_enabled + coords: сначала «свой город»/близко, затем по distance.
    """
    from services.app_settings_service import get_setting_bool
    from services.geo_service import (
        geo_bbox_clauses,
        has_coords,
        same_city_rank_expr,
        sql_distance_order,
        sql_haversine_km,
    )

    exclude_ids = exclude_ids or []
    now = datetime.now(timezone.utc)

    liked = exists(
        select(Like.id).where(
            Like.from_user_id == viewer.id,
            Like.to_user_id == User.id,
        )
    )
    skipped = exists(
        select(ProfileSkip.id).where(
            ProfileSkip.from_user_id == viewer.id,
            ProfileSkip.to_user_id == User.id,
        )
    )

    conditions = [
        User.id != viewer.id,
        User.profile_completed.is_(True),
        User.disabled.is_(False),
        User.is_banned.is_(False),
        ~liked,
        ~skipped,
    ]
    if exclude_ids:
        conditions.append(~User.id.in_(exclude_ids))

    # seeking → пол анкет в ленте «Оценивать»
    if await get_setting_bool(session, "feed_filter_seeking"):
        if viewer.seeking == "men":
            conditions.append(User.gender == "male")
        elif viewer.seeking == "women":
            conditions.append(User.gender == "female")

    # visible_to кандидата: кому разрешено видеть анкету
    if await get_setting_bool(session, "feed_filter_visible_to"):
        if viewer.gender == "male":
            conditions.append(or_(User.visible_to.is_(None), User.visible_to.in_(("all", "men"))))
        elif viewer.gender == "female":
            conditions.append(or_(User.visible_to.is_(None), User.visible_to.in_(("all", "women"))))
        else:
            # пол зрителя неизвестен — только анкеты «для всех»
            conditions.append(or_(User.visible_to.is_(None), User.visible_to == "all"))

    geo_enabled = await get_setting_bool(session, "geo_search_enabled")
    use_geo = geo_enabled and has_coords(viewer)
    filter_city = await get_setting_bool(session, "feed_filter_city")

    if use_geo and filter_city:
        # Только в радиусе nearby
        radius = settings.geo_nearby_radius_km
        conditions.extend(
            geo_bbox_clauses(User.latitude, User.longitude, viewer.latitude, viewer.longitude, radius)
        )
        dist = sql_haversine_km(User.latitude, User.longitude, viewer.latitude, viewer.longitude)
        conditions.append(dist <= radius)
    elif not use_geo and filter_city and viewer.city:
        conditions.append(func.lower(User.city) == viewer.city.strip().lower())

    premium_rank = case((User.premium_until > now, 1), else_=0)
    order = []
    if use_geo:
        same = same_city_rank_expr(
            User.city,
            User.latitude,
            User.longitude,
            viewer_city=viewer.city,
            viewer_lat=viewer.latitude,
            viewer_lon=viewer.longitude,
            same_city_km=settings.geo_same_city_km,
        )
        order.extend(
            [
                same.desc(),
                sql_distance_order(User.latitude, User.longitude, viewer.latitude, viewer.longitude),
            ]
        )
    order.extend(
        [
            premium_rank.desc(),
            User.premium_until.desc().nullslast(),
            User.rating_avg.desc(),
            User.id,
        ]
    )

    query = select(User).options(selectinload(User.goal)).where(and_(*conditions))
    result = await session.execute(query.order_by(*order).limit(1))
    return result.scalar_one_or_none()


async def recalculate_rating(session: AsyncSession, user_id: int) -> None:
    result = await session.execute(
        select(func.avg(Rating.stars), func.count(Rating.id)).where(Rating.to_user_id == user_id)
    )
    avg, count = result.one()
    user = await session.get(User, user_id)
    if user:
        user.rating_avg = float(avg or 0)
        user.rating_count = int(count or 0)
