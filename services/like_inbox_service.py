"""Пакетные уведомления о входящих лайках (порог 3)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Like, User

LIKE_INBOX_THRESHOLD = 3
REDIS_INBOX_MSG = "like_inbox_msg:{user_id}"
REDIS_INBOX_ACTIVE = "like_inbox_active:{user_id}"
REDIS_INBOX_TTL = 60 * 60 * 24 * 14


async def count_unseen_likes(session: AsyncSession, to_user_id: int) -> int:
    result = await session.execute(
        select(func.count(Like.id)).where(
            Like.to_user_id == to_user_id,
            Like.seen_by_target_at.is_(None),
        )
    )
    return int(result.scalar_one() or 0)


async def list_unseen_likes(session: AsyncSession, to_user_id: int, *, limit: int = 50) -> list[Like]:
    result = await session.execute(
        select(Like)
        .where(Like.to_user_id == to_user_id, Like.seen_by_target_at.is_(None))
        .order_by(Like.created_at.asc(), Like.id.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_next_unseen_like(session: AsyncSession, to_user_id: int) -> Like | None:
    likes = await list_unseen_likes(session, to_user_id, limit=1)
    return likes[0] if likes else None


async def mark_like_seen(session: AsyncSession, like: Like) -> None:
    if like.seen_by_target_at is None:
        like.seen_by_target_at = datetime.now(timezone.utc)


async def mark_like_seen_from_user(
    session: AsyncSession, *, to_user_id: int, from_user_id: int
) -> None:
    result = await session.execute(
        select(Like).where(
            Like.to_user_id == to_user_id,
            Like.from_user_id == from_user_id,
            Like.seen_by_target_at.is_(None),
        )
    )
    like = result.scalar_one_or_none()
    if like:
        await mark_like_seen(session, like)


async def set_inbox_message(redis, user_id: int, chat_id: int, message_id: int) -> None:
    if redis is None:
        return
    await redis.set(
        REDIS_INBOX_MSG.format(user_id=user_id),
        f"{chat_id}:{message_id}",
        ex=REDIS_INBOX_TTL,
    )


async def get_inbox_message(redis, user_id: int) -> tuple[int, int] | None:
    if redis is None:
        return None
    raw = await redis.get(REDIS_INBOX_MSG.format(user_id=user_id))
    if not raw:
        return None
    try:
        chat_s, msg_s = str(raw).split(":", 1)
        return int(chat_s), int(msg_s)
    except (TypeError, ValueError):
        return None


async def clear_inbox_message(redis, user_id: int) -> None:
    if redis is None:
        return
    await redis.delete(REDIS_INBOX_MSG.format(user_id=user_id))


async def set_inbox_browsing(redis, user_id: int, active: bool) -> None:
    if redis is None:
        return
    key = REDIS_INBOX_ACTIVE.format(user_id=user_id)
    if active:
        await redis.set(key, "1", ex=REDIS_INBOX_TTL)
    else:
        await redis.delete(key)


async def is_inbox_browsing(redis, user_id: int) -> bool:
    if redis is None:
        return False
    return bool(await redis.get(REDIS_INBOX_ACTIVE.format(user_id=user_id)))


async def notify_like_batch_if_needed(
    bot,
    session: AsyncSession,
    target: User,
    *,
    redis=None,
) -> None:
    """Если непросмотренных лайков >= 3 — отправить/обновить одно уведомление."""
    from bot.keyboards.keyboards import like_inbox_offer_kb
    from bot.texts.i18n import lang_of, t

    n = await count_unseen_likes(session, target.id)
    if n < LIKE_INBOX_THRESHOLD:
        return

    text = t(target, "LIKE_NOTIFY_BATCH", n=n)
    kb = like_inbox_offer_kb(lang_of(target))
    existing = await get_inbox_message(redis, target.id)
    if existing:
        chat_id, message_id = existing
        try:
            await bot.edit_message_text(
                text, chat_id=chat_id, message_id=message_id, reply_markup=kb
            )
            return
        except Exception:
            pass

    try:
        sent = await bot.send_message(target.telegram_id, text, reply_markup=kb)
        await set_inbox_message(redis, target.id, sent.chat.id, sent.message_id)
    except Exception:
        pass
