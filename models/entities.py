"""Модели базы данных."""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class Seeking(str, Enum):
    MEN = "men"
    WOMEN = "women"
    BOTH = "both"


class VisibleTo(str, Enum):
    MEN = "men"
    WOMEN = "women"
    ALL = "all"


class Country(str, Enum):
    RUSSIA = "russia"
    BELARUS = "belarus"
    KAZAKHSTAN = "kazakhstan"
    UKRAINE = "ukraine"


class ComplaintType(str, Enum):
    USER = "user"
    EVENT = "event"


class ComplaintStatus(str, Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class AdminDecision(str, Enum):
    BLOCK = "block"
    WARNING = "warning"
    REJECT = "reject"


class EventStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    DELETED = "deleted"


class ApplicationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class VerificationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReferralTrack(str, Enum):
    STANDARD = "standard"
    BLOGGER = "blogger"


class WithdrawStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REJECTED = "rejected"


class BroadcastStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    CANCELED = "canceled"


class PaymentProvider(str, Enum):
    YOOKASSA = "yookassa"
    STARS = "stars"


class User(Base):
    """Пользователь бота."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="ru")
    country: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    seeking: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    visible_to: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    profile_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    sparks_balance: Mapped[int] = mapped_column(Integer, default=0)
    rating_avg: Mapped[float] = mapped_column(Float, default=0.0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    events_attended: Mapped[int] = mapped_column(Integer, default=0)
    events_organized: Mapped[int] = mapped_column(Integer, default=0)
    premium_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    referral_code: Mapped[Optional[str]] = mapped_column(String(32), unique=True, nullable=True)
    referred_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    referral_track: Mapped[str] = mapped_column(String(16), default=ReferralTrack.STANDARD.value)
    referral_count: Mapped[int] = mapped_column(Integer, default=0)
    free_rating_reset_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    goal: Mapped[Optional["Goal"]] = relationship(back_populates="user", uselist=False)
    referred_by: Mapped[Optional["User"]] = relationship(remote_side=[id])


class Goal(Base):
    """Цель пользователя."""

    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    target_sparks: Mapped[int] = mapped_column(Integer)
    collected_sparks: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="goal")


class Like(Base):
    """Лайк между пользователями."""

    __tablename__ = "likes"
    __table_args__ = (UniqueConstraint("from_user_id", "to_user_id", name="uq_like_pair"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProfileSkip(Base):
    """Пропуск анкеты в ленте «Оценивать» — больше не показывать."""

    __tablename__ = "profile_skips"
    __table_args__ = (UniqueConstraint("from_user_id", "to_user_id", name="uq_profile_skip_pair"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Rating(Base):
    """Оценка анкеты."""

    __tablename__ = "ratings"
    __table_args__ = (UniqueConstraint("from_user_id", "to_user_id", name="uq_rating_pair"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    stars: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Match(Base):
    """Взаимный лайк."""

    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("user1_id", "user2_id", name="uq_match_pair"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user1_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user2_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Support(Base):
    """Поддержка цели пользователя."""

    __tablename__ = "supports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    fee: Mapped[int] = mapped_column(Integer, default=0)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SparksTransaction(Base):
    """Транзакция Искр."""

    __tablename__ = "sparks_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    tx_type: Mapped[str] = mapped_column(String(32), index=True)
    reference_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Payment(Base):
    """Платёж (ЮKassa / Telegram Stars)."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(16), default=PaymentProvider.YOOKASSA.value, index=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True, index=True)
    amount_sparks: Mapped[int] = mapped_column(Integer)
    amount_rub: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default=PaymentStatus.PENDING.value, index=True)
    purpose: Mapped[str] = mapped_column(String(32), default="buy_sparks")
    confirmation_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    is_stub: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Event(Base):
    """Мероприятие (тусовка)."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organizer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(String(512))
    event_date: Mapped[str] = mapped_column(String(64))
    event_time: Mapped[str] = mapped_column(String(32))
    price: Mapped[int] = mapped_column(Integer, default=0)
    men_needed: Mapped[int] = mapped_column(Integer, default=0)
    women_needed: Mapped[int] = mapped_column(Integer, default=0)
    men_count: Mapped[int] = mapped_column(Integer, default=0)
    women_count: Mapped[int] = mapped_column(Integer, default=0)
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=EventStatus.ACTIVE.value, index=True)
    mass_invites_used: Mapped[int] = mapped_column(Integer, default=0)
    pinned_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    boosted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    group_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EventApplication(Base):
    """Заявка на участие в тусовке."""

    __tablename__ = "event_applications"
    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_event_application"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default=ApplicationStatus.PENDING.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Complaint(Base):
    """Жалоба на пользователя или мероприятие."""

    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    target_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), nullable=True)
    complaint_type: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=ComplaintStatus.PENDING.value, index=True)
    admin_decision: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    admin_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Verification(Base):
    """Заявка на верификацию."""

    __tablename__ = "verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    code: Mapped[str] = mapped_column(String(16))
    gesture: Mapped[str] = mapped_column(String(32))
    video_file_id: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=VerificationStatus.PENDING.value, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Referral(Base):
    """Реферальная связь."""

    __tablename__ = "referrals"
    __table_args__ = (UniqueConstraint("referrer_id", "referred_id", name="uq_referral_pair"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    referred_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    counted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReferralReward(Base):
    """Награда за реферальный порог."""

    __tablename__ = "referral_rewards"
    __table_args__ = (UniqueConstraint("user_id", "threshold", name="uq_referral_reward"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    threshold: Mapped[int] = mapped_column(Integer)
    reward_type: Mapped[str] = mapped_column(String(64))
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WithdrawRequest(Base):
    """Заявка на вывод Искр."""

    __tablename__ = "withdraw_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    fee: Mapped[int] = mapped_column(Integer)
    net_amount: Mapped[int] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(16), default="requisites", index=True)  # stars | requisites
    requisites: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=WithdrawStatus.PENDING.value, index=True)
    payout_meta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AppSetting(Base):
    """Настройки приложения."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    value: Mapped[str] = mapped_column(Text)


class Broadcast(Base):
    """Массовая рассылка."""

    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(BigInteger)
    message_text: Mapped[str] = mapped_column(Text)
    filters_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_user_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=BroadcastStatus.PENDING.value)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EventCategory(Base):
    """Категория мероприятий."""

    __tablename__ = "event_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    emoji: Mapped[str] = mapped_column(String(8), default="")
    filter_type: Mapped[str] = mapped_column(String(16), default="type")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BloggerProfile(Base):
    """Партнёрский профиль блогера."""

    __tablename__ = "blogger_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending/approved/rejected
    views: Mapped[int] = mapped_column(Integer, default=0)
    total_commission: Mapped[int] = mapped_column(Integer, default=0)
    reward_500k_claimed: Mapped[bool] = mapped_column(Boolean, default=False)
    reward_1m_claimed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MatchMessage(Base):
    """Сообщение в чате мэтча внутри бота (заготовка)."""

    __tablename__ = "match_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
