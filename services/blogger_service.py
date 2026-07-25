"""Партнёрская (блогерская) программа."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models import User
from models.entities import BloggerProfile, ReferralTrack
from services.sparks_service import add_transaction

settings = get_settings()
COMMISSION_RATE = 0.15  # 15% от покупок Premium рефералами
VIEWS_REWARD_500K = 1000
VIEWS_REWARD_1M = 2000
PROFILES_PER_REWARD = 100
PROFILES_REWARD_SPARKS = 300


async def get_or_create_blogger(session: AsyncSession, user: User) -> BloggerProfile:
    result = await session.execute(select(BloggerProfile).where(BloggerProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if profile:
        return profile
    profile = BloggerProfile(user_id=user.id, status="pending")
    session.add(profile)
    await session.flush()
    return profile


async def apply_blogger(session: AsyncSession, user: User) -> BloggerProfile:
    profile = await get_or_create_blogger(session, user)
    if profile.status == "rejected":
        profile.status = "pending"
    user.referral_track = ReferralTrack.BLOGGER.value
    return profile


async def approve_blogger(session: AsyncSession, user_id: int) -> BloggerProfile:
    result = await session.execute(select(BloggerProfile).where(BloggerProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        profile = BloggerProfile(user_id=user_id)
        session.add(profile)
    profile.status = "approved"
    user = await session.get(User, user_id)
    if user:
        user.referral_track = ReferralTrack.BLOGGER.value
    await session.flush()
    return profile


async def reject_blogger(session: AsyncSession, user_id: int) -> None:
    result = await session.execute(select(BloggerProfile).where(BloggerProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if profile:
        profile.status = "rejected"


async def record_blogger_view(session: AsyncSession, referrer: User) -> None:
    """Учесть просмотр по реферальной ссылке блогера."""
    if referrer.referral_track != ReferralTrack.BLOGGER.value:
        return
    result = await session.execute(select(BloggerProfile).where(BloggerProfile.user_id == referrer.id))
    profile = result.scalar_one_or_none()
    if not profile or profile.status != "approved":
        return
    profile.views += 1
    await _maybe_claim_view_rewards(session, referrer, profile)


async def _maybe_claim_view_rewards(session: AsyncSession, user: User, profile: BloggerProfile) -> None:
    if profile.views >= 500_000 and not profile.reward_500k_claimed:
        profile.reward_500k_claimed = True
        await add_transaction(session, user.id, VIEWS_REWARD_500K, "blogger_views_500k")
    if profile.views >= 1_000_000 and not profile.reward_1m_claimed:
        profile.reward_1m_claimed = True
        await add_transaction(session, user.id, VIEWS_REWARD_1M, "blogger_views_1m")


async def maybe_reward_blogger_profiles(session: AsyncSession, referrer: User) -> int:
    """За каждые 100 анкет по ссылке блогера — 300 искр. Возвращает начисленные искры."""
    if referrer.referral_track != ReferralTrack.BLOGGER.value:
        return 0
    result = await session.execute(select(BloggerProfile).where(BloggerProfile.user_id == referrer.id))
    profile = result.scalar_one_or_none()
    if not profile or profile.status != "approved":
        return 0

    from services.referral_service import count_completed_referrals

    completed = await count_completed_referrals(session, referrer.id)
    batches_earned = completed // PROFILES_PER_REWARD
    already = profile.profiles_reward_batches or 0
    if batches_earned <= already:
        return 0

    total = 0
    for batch_no in range(already + 1, batches_earned + 1):
        await add_transaction(
            session,
            referrer.id,
            PROFILES_REWARD_SPARKS,
            "blogger_profiles_100",
            metadata=str(batch_no * PROFILES_PER_REWARD),
        )
        total += PROFILES_REWARD_SPARKS
    profile.profiles_reward_batches = batches_earned
    return total


async def pay_blogger_commission(
    session: AsyncSession,
    buyer: User,
    sparks_spent: int,
    *,
    purpose: str = "purchase",
) -> int:
    """15% от покупки Premium рефералом — блогеру."""
    if purpose != "premium":
        return 0
    if sparks_spent <= 0 or not buyer.referred_by_id:
        return 0
    referrer = await session.get(User, buyer.referred_by_id)
    if not referrer or referrer.referral_track != ReferralTrack.BLOGGER.value:
        return 0
    result = await session.execute(select(BloggerProfile).where(BloggerProfile.user_id == referrer.id))
    profile = result.scalar_one_or_none()
    if not profile or profile.status != "approved":
        return 0
    commission = max(1, int(sparks_spent * COMMISSION_RATE))
    await add_transaction(
        session,
        referrer.id,
        commission,
        "blogger_commission",
        buyer.id,
        metadata=purpose,
    )
    profile.total_commission += commission
    return commission


def blogger_link(user: User) -> str:
    code = user.referral_code or str(user.id)
    return f"https://t.me/{settings.bot_username}?start=ref_{code}"
