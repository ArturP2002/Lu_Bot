"""Реферальная программа по ТЗ."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Referral, ReferralReward, User
from services.sparks_service import add_transaction

# 1–4 → Premium 1м; 5–9 → Premium 3м; 10–24 → Premium 12м;
# 25+ → Premium навсегда + статус Блогер
REFERRAL_THRESHOLDS = {
    1: ("premium_1m", 30, 0),
    5: ("premium_3m", 90, 0),
    10: ("premium_12m", 365, 0),
    25: ("premium_forever_blogger", -1, 0),
}

BLOGGER_UNLOCK_THRESHOLD = 25


async def count_completed_referrals(session: AsyncSession, referrer_id: int) -> int:
    """Реальные рефералы с заполненной анкетой и успешной верификацией."""
    result = await session.execute(
        select(func.count(Referral.id))
        .join(User, User.id == Referral.referred_id)
        .where(
            Referral.referrer_id == referrer_id,
            User.profile_completed.is_(True),
            User.verified.is_(True),
        )
    )
    return result.scalar() or 0


async def process_referral_on_profile_complete(session: AsyncSession, user: User) -> None:
    """Засчитать реферала только после заполнения анкеты и верификации."""
    if not user.referred_by_id or not user.profile_completed or not user.verified:
        return

    # Сериализуем начисления одному пригласившему: счет и награды не теряются
    # при одновременной верификации нескольких приглашённых.
    referrer = await session.scalar(
        select(User).where(User.id == user.referred_by_id).with_for_update()
    )
    if not referrer:
        return

    existing = await session.execute(
        select(Referral).where(
            Referral.referrer_id == user.referred_by_id,
            Referral.referred_id == user.id,
        )
    )
    referral = existing.scalar_one_or_none()
    if not referral:
        referral = Referral(referrer_id=user.referred_by_id, referred_id=user.id)
        session.add(referral)

    if not referral.counted_at:
        referral.counted_at = datetime.now(timezone.utc)

    referrer.referral_count = await count_completed_referrals(session, referrer.id)
    from services.blogger_service import maybe_auto_unlock_blogger, maybe_reward_blogger_profiles

    await maybe_auto_unlock_blogger(session, referrer)
    await maybe_reward_blogger_profiles(session, referrer)


async def process_referral_on_verification(session: AsyncSession, user: User) -> None:
    """Засчитать подтверждённого реферала."""
    await process_referral_on_profile_complete(session, user)


def _effective_threshold(count: int) -> list[int]:
    return [th for th in REFERRAL_THRESHOLDS if count >= th]


async def get_available_rewards(session: AsyncSession, user: User) -> list[dict]:
    count = await count_completed_referrals(session, user.id)
    claimed = await session.execute(
        select(ReferralReward.threshold).where(ReferralReward.user_id == user.id)
    )
    claimed_thresholds = {r for r in claimed.scalars().all()}

    available = []
    for threshold in _effective_threshold(count):
        if threshold not in claimed_thresholds and threshold in REFERRAL_THRESHOLDS:
            reward_type, days, sparks = REFERRAL_THRESHOLDS[threshold]
            available.append(
                {
                    "threshold": threshold,
                    "reward_type": reward_type,
                    "days": days,
                    "sparks": sparks,
                }
            )
    return available


async def claim_referral_reward(session: AsyncSession, user: User, threshold: int) -> str:
    available = await get_available_rewards(session, user)
    if not any(r["threshold"] == threshold for r in available):
        raise ValueError("Награда недоступна")

    reward_type, days, sparks = REFERRAL_THRESHOLDS[threshold]
    reward = ReferralReward(user_id=user.id, threshold=threshold, reward_type=reward_type)
    reward.claimed_at = datetime.now(timezone.utc)
    session.add(reward)

    if days:
        now = datetime.now(timezone.utc)
        if days == -1:
            user.premium_until = datetime(2099, 12, 31, tzinfo=timezone.utc)
        else:
            base = user.premium_until if user.premium_until and user.premium_until > now else now
            if base.tzinfo is None:
                base = base.replace(tzinfo=timezone.utc)
            user.premium_until = base + timedelta(days=days)

    if sparks > 0:
        await add_transaction(session, user.id, sparks, "referral_reward", threshold)

    if threshold >= BLOGGER_UNLOCK_THRESHOLD:
        from services.blogger_service import maybe_auto_unlock_blogger

        await maybe_auto_unlock_blogger(session, user)

    return reward_type


def referral_ranking_query():
    """Единый рейтинг: реальные подтверждённые приглашения + ручной бонус.

    При равном счёте первым идёт меньший ID. В рейтинге все заполненные
    незаблокированные анкеты, включая пользователей без приглашений.
    """
    counts = (
        select(Referral.referrer_id, func.count(Referral.id).label("verified_count"))
        .join(User, User.id == Referral.referred_id)
        .where(User.profile_completed.is_(True), User.verified.is_(True))
        .group_by(Referral.referrer_id).subquery()
    )
    actual = func.coalesce(counts.c.verified_count, 0)
    score = actual + User.referral_leaderboard_bonus
    return (
        select(
            User.id, User.display_name, User.username, User.telegram_id,
            User.referral_code, User.referral_track,
            actual.label("referral_count"),
            User.referral_leaderboard_bonus.label("leaderboard_bonus"),
            score.label("leaderboard_count"),
            func.row_number().over(order_by=(score.desc(), User.id.asc())).label("rank"),
        )
        .outerjoin(counts, counts.c.referrer_id == User.id)
        .where(User.profile_completed.is_(True), User.is_banned.is_(False))
    )


async def get_referral_leaderboard(session: AsyncSession, user_id: int) -> tuple[list[dict], dict | None]:
    ranked = referral_ranking_query().subquery()
    top = await session.execute(select(ranked).order_by(ranked.c.rank).limit(5))
    own = await session.execute(select(ranked).where(ranked.c.id == user_id))
    return [dict(row) for row in top.mappings()], next((dict(row) for row in own.mappings()), None)
