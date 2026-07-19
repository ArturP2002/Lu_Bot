"""Сервис взаимных лайков."""

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Like, Match, User


async def check_mutual_like(session: AsyncSession, from_user: User, to_user: User) -> bool:
    """Проверить взаимный лайк и создать матч."""
    result = await session.execute(
        select(Like).where(Like.from_user_id == to_user.id, Like.to_user_id == from_user.id)
    )
    reverse_like = result.scalar_one_or_none()
    if not reverse_like:
        return False

    existing = await session.execute(
        select(Match).where(
            or_(
                (Match.user1_id == from_user.id) & (Match.user2_id == to_user.id),
                (Match.user1_id == to_user.id) & (Match.user2_id == from_user.id),
            )
        )
    )
    if existing.scalar_one_or_none():
        return False  # уже был мэтч — повторно не уведомляем

    match = Match(user1_id=min(from_user.id, to_user.id), user2_id=max(from_user.id, to_user.id))
    session.add(match)
    await session.flush()
    return True
