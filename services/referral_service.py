"""Реферальная программа по ТЗ."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Referral, ReferralReward, User
from services.sparks_service import add_transaction

# ТЗ: диапазоны → награда при достижении нижней границы
# 1–3 → Premium 1м; 4–5 → Premium 3м; 6–10 → 200 искр;
# 11–100 → 300 искр + Premium 6м; 100+ → 1000 искр + Premium навсегда
REFERRAL_THRESHOLDS = {
    1: ("premium_1m", 30, 0),
    4: ("premium_3m", 90, 0),
    6: ("sparks_200", 0, 200),
    11: ("sparks_300_premium_6m", 180, 300),
    100: ("sparks_1000_premium_forever", -1, 1000),
}


async def count_completed_referrals(session: AsyncSession, referrer_id: int) -> int:
    """Рефералы с завершённой анкетой (по ТЗ — после создания анкеты)."""
    result = await session.execute(
        select(func.count(Referral.id))
        .join(User, User.id == Referral.referred_id)
        .where(
            Referral.referrer_id == referrer_id,
            User.profile_completed.is_(True),
        )
    )
    return result.scalar() or 0


async def process_referral_on_profile_complete(session: AsyncSession, user: User) -> None:
    """Засчитать реферала после создания анкеты."""
    if not user.referred_by_id or not user.profile_completed:
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

    referrer = await session.get(User, user.referred_by_id)
    if referrer:
        referrer.referral_count = await count_completed_referrals(session, referrer.id)


async def process_referral_on_verification(session: AsyncSession, user: User) -> None:
    """Обратная совместимость: также засчитываем при верификации."""
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

    return reward_type
