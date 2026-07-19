"""Сервис ленты анкет."""

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import Like, Rating, User


async def get_next_profile(session: AsyncSession, viewer: User, exclude_ids: list[int] | None = None) -> User | None:
    """Получить следующую анкету для просмотра."""
    from services.app_settings_service import get_setting_bool

    exclude_ids = exclude_ids or []

    liked_subq = select(Like.to_user_id).where(Like.from_user_id == viewer.id)

    conditions = [
        User.id != viewer.id,
        User.profile_completed.is_(True),
        User.disabled.is_(False),
        User.is_banned.is_(False),
        ~User.id.in_(liked_subq),
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

    # город
    if await get_setting_bool(session, "feed_filter_city") and viewer.city:
        conditions.append(func.lower(User.city) == viewer.city.strip().lower())

    query = select(User).options(selectinload(User.goal)).where(and_(*conditions))
    result = await session.execute(query.order_by(User.premium_until.desc().nullslast(), User.id).limit(1))
    return result.scalar_one_or_none()


async def recalculate_rating(session: AsyncSession, user_id: int) -> None:
    """Пересчитать средний рейтинг пользователя."""
    result = await session.execute(select(Rating).where(Rating.to_user_id == user_id))
    ratings = result.scalars().all()
    user = await session.get(User, user_id)
    if not user:
        return
    if not ratings:
        user.rating_avg = 0.0
        user.rating_count = 0
    else:
        user.rating_count = len(ratings)
        user.rating_avg = round(sum(r.stars for r in ratings) / len(ratings), 1)
