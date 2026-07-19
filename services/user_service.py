"""Вспомогательные функции для пользователей."""

import secrets
import string
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import Goal, User


def is_premium(user: User) -> bool:
    """Проверка активной Premium-подписки."""
    if not user.premium_until:
        return False
    now = datetime.now(timezone.utc)
    premium_until = user.premium_until
    if premium_until.tzinfo is None:
        premium_until = premium_until.replace(tzinfo=timezone.utc)
    return premium_until > now


def generate_referral_code(length: int = 8) -> str:
    """Генерация уникального реферального кода."""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    """Получить пользователя по Telegram ID."""
    result = await session.execute(
        select(User).options(selectinload(User.goal)).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str | None = None) -> User:
    """Получить или создать пользователя."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        if username and user.username != username:
            user.username = username
        return user

    code = generate_referral_code()
    while True:
        exists = await session.execute(select(User).where(User.referral_code == code))
        if not exists.scalar_one_or_none():
            break
        code = generate_referral_code()

    user = User(telegram_id=telegram_id, username=username, referral_code=code)
    session.add(user)
    await session.flush()
    return user


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    """Получить пользователя по внутреннему ID."""
    result = await session.execute(
        select(User).options(selectinload(User.goal)).where(User.id == user_id)
    )
    return result.scalar_one_or_none()
