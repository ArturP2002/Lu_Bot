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


async def revoke_blogger(session: AsyncSession, user_id: int) -> BloggerProfile | None:
    """Снять статус блогера (админка). Авто-выдача больше не вернёт статус."""
    result = await session.execute(select(BloggerProfile).where(BloggerProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        return None
    profile.status = "rejected"
    user = await session.get(User, user_id)
    if user:
        user.referral_track = ReferralTrack.STANDARD.value
    await session.flush()
    return profile


async def reject_blogger(session: AsyncSession, user_id: int) -> None:
    """Обратная совместимость: снять статус блогера."""
    await revoke_blogger(session, user_id)


async def is_blogger_revoked(session: AsyncSession, user: User) -> bool:
    result = await session.execute(select(BloggerProfile).where(BloggerProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    return bool(profile and profile.status == "rejected")


async def is_blogger_eligible(session: AsyncSession, user: User) -> bool:
    """Блогерка открывается при 25+ друзьях (финальный бонус обычной рефералки)."""
    from models import ReferralReward
    from services.referral_service import BLOGGER_UNLOCK_THRESHOLD, count_completed_referrals

    result = await session.execute(select(BloggerProfile).where(BloggerProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if profile and profile.status == "approved":
        return True
    # Админ снял статус — без ручного возврата не выдаём снова
    if profile and profile.status == "rejected":
        return False

    count = await count_completed_referrals(session, user.id)
    if count >= BLOGGER_UNLOCK_THRESHOLD:
        return True

    claimed = await session.execute(
        select(ReferralReward.threshold).where(
            ReferralReward.user_id == user.id,
            ReferralReward.threshold >= BLOGGER_UNLOCK_THRESHOLD,
        )
    )
    return claimed.scalars().first() is not None


async def maybe_auto_unlock_blogger(session: AsyncSession, user: User) -> BloggerProfile | None:
    """Автоматически выдать статус блогера без одобрения админа, если доступен."""
    if not await is_blogger_eligible(session, user):
        return None
    return await approve_blogger(session, user.id)


async def apply_blogger(session: AsyncSession, user: User) -> BloggerProfile | None:
    """Открыть блогер-программу. Без заявки админу — только после разблокировки рефералкой."""
    if not await is_blogger_eligible(session, user):
        return None
    return await approve_blogger(session, user.id)


async def record_blogger_view(session: AsyncSession, referrer: User) -> None:
    """Учесть просмотр по реферальной ссылке блогера."""
    if referrer.referral_track != ReferralTrack.BLOGGER.value:
        return
    result = await session.execute(select(BloggerProfile).where(BloggerProfile.user_id == referrer.id))
    profile = result.scalar_one_or_none()
    if not profile or profile.status != "approved":
        return
    profile.views += 1


async def _maybe_claim_view_rewards(session: AsyncSession, user: User, profile: BloggerProfile) -> None:
    """Награды за просмотры отключены — оставлено для совместимости админки."""
    return


async def maybe_reward_blogger_profiles(session: AsyncSession, referrer: User) -> int:
    """За каждые 100 анкет по ссылке блогера — 300 искр. Возвращает начисленные искры."""
    from sqlalchemy import func

    from models import SparksTransaction
    from services.referral_service import count_completed_referrals

    if referrer.referral_track != ReferralTrack.BLOGGER.value:
        return 0
    result = await session.execute(select(BloggerProfile).where(BloggerProfile.user_id == referrer.id))
    profile = result.scalar_one_or_none()
    if not profile or profile.status != "approved":
        return 0

    completed = await count_completed_referrals(session, referrer.id)
    batches_earned = completed // PROFILES_PER_REWARD
    already = await session.scalar(
        select(func.count(SparksTransaction.id)).where(
            SparksTransaction.user_id == referrer.id,
            SparksTransaction.tx_type == "blogger_profiles_100",
        )
    ) or 0
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
