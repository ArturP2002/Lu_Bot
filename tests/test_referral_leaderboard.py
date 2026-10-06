"""Регрессии партнерки: SQL-рейтинг, начисления и доступ без верификации."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.database import Base
from models import Referral, User
from services.referral_service import (
    count_completed_referrals,
    get_available_rewards,
    get_referral_leaderboard,
    process_referral_on_profile_complete,
    process_referral_on_verification,
)


async def with_database(check):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await check(session)
    finally:
        await engine.dispose()


def test_referral_requires_verification_and_is_idempotent():
    async def check(session):
        owner = User(telegram_id=1, profile_completed=True)
        session.add(owner)
        await session.flush()
        invited = User(telegram_id=2, profile_completed=True, referred_by_id=owner.id)
        session.add(invited)
        await session.flush()
        await process_referral_on_profile_complete(session, invited)
        assert await count_completed_referrals(session, owner.id) == 0
        assert await get_available_rewards(session, owner) == []
        invited.verified = True
        await process_referral_on_verification(session, invited)
        await process_referral_on_verification(session, invited)
        assert await count_completed_referrals(session, owner.id) == 1
        assert await session.scalar(select(func.count(Referral.id))) == 1
        assert owner.referral_count == 1
        referral = await session.scalar(select(Referral))
        assert referral.counted_at is not None
        assert [r['threshold'] for r in await get_available_rewards(session, owner)] == [1]
    asyncio.run(with_database(check))


def test_top_five_ties_own_rank_bonus_and_ineligible_users():
    async def check(session):
        users = [User(telegram_id=i, profile_completed=True, referral_leaderboard_bonus=8-i) for i in range(1, 8)]
        users += [User(telegram_id=100, profile_completed=False, referral_leaderboard_bonus=999),
                  User(telegram_id=101, profile_completed=True, is_banned=True, referral_leaderboard_bonus=999)]
        session.add_all(users)
        await session.flush()
        users[1].referral_leaderboard_bonus = users[0].referral_leaderboard_bonus
        top, own = await get_referral_leaderboard(session, users[6].id)
        assert len(top) == 5
        assert [row['id'] for row in top] == [user.id for user in users[:5]]
        assert own['rank'] == 7
        assert own['leaderboard_count'] == 1
        assert await get_available_rewards(session, users[0]) == []
        users[6].referral_leaderboard_bonus = 20
        top, own = await get_referral_leaderboard(session, users[6].id)
        assert top[0]['id'] == users[6].id and own['rank'] == 1
        users[6].referral_leaderboard_bonus = 0
        _, own = await get_referral_leaderboard(session, users[6].id)
        assert own['rank'] == 7 and own['leaderboard_count'] == 0
    asyncio.run(with_database(check))


def test_ranking_counts_verified_profiles_even_with_stale_cache():
    async def check(session):
        owner = User(telegram_id=1, profile_completed=True, referral_count=99)
        session.add(owner)
        await session.flush()
        for i, (completed, verified) in enumerate([(True, True), (True, False), (False, True)], 2):
            invited = User(telegram_id=i, profile_completed=completed, verified=verified)
            session.add(invited)
            await session.flush()
            session.add(Referral(referrer_id=owner.id, referred_id=invited.id))
        top, own = await get_referral_leaderboard(session, owner.id)
        assert own['leaderboard_count'] == 1
        assert top[0]['referral_count'] == 1
        assert await count_completed_referrals(session, owner.id) == 1
    asyncio.run(with_database(check))


@pytest.mark.parametrize('lang', ['ru', 'be', 'kk', 'uk'])
def test_profile_has_no_party_counters_and_badge_requires_verification(lang):
    from bot.texts.formatters import format_other_profile, format_own_profile
    from bot.keyboards.keyboards import menu_kb_for, referral_kb
    from bot.texts.i18n import t
    from bot.texts.ui_labels import lbl
    user = User(telegram_id=1, language=lang, display_name='Test', age=25, goal=None,
                verified=False, events_attended=123456, events_organized=654321)
    for formatter in (format_own_profile, format_other_profile):
        text = formatter(user, lang)
        assert '123456' not in text and '654321' not in text
        assert '✅' not in text
        user.verified = True
        assert '✅' in formatter(user, lang)
        user.verified = False
    assert len(menu_kb_for(user).keyboard) == 3
    assert any(b.callback_data == 'ref:leaderboard' for row in referral_kb(lang).inline_keyboard for b in row)
    assert t(lang, 'LEADERBOARD_TITLE') != 'LEADERBOARD_TITLE'
    assert lbl(lang, 'prof_referral') != 'Реферальная программа💸'


def test_registration_skips_goal_and_rating_is_available_without_verification(monkeypatch):
    from bot.handlers import registration, menu, rating, luma
    from bot.states.states import Registration
    user = User(telegram_id=1, verified=False)
    state = AsyncMock()
    callback = AsyncMock()
    monkeypatch.setattr(registration, '_send_profile_preview', AsyncMock())
    monkeypatch.setattr(registration, 'strip_inline_keyboard', AsyncMock())
    asyncio.run(registration.reg_bio_skip(callback, state, user, AsyncMock()))
    state.set_state.assert_awaited_once_with(Registration.preview)
    monkeypatch.setattr(menu, '_open_from_menu', AsyncMock())
    monkeypatch.setattr(luma, 'clear_luma_browse', AsyncMock())
    show = AsyncMock()
    monkeypatch.setattr(rating, 'show_next_profile', show)
    asyncio.run(menu.menu_rate(AsyncMock(), state, user, AsyncMock(), AsyncMock()))
    show.assert_awaited_once()


def test_leaderboard_escapes_names(monkeypatch):
    from bot.handlers.profile import _partner_text
    import services.referral_service as service
    monkeypatch.setattr(service, 'get_referral_leaderboard', AsyncMock(return_value=(
        [{'rank': 1, 'id': 1, 'display_name': '<b>name</b>', 'username': None, 'leaderboard_count': 3}],
        {'rank': 6, 'leaderboard_count': 0})))
    text = asyncio.run(_partner_text(AsyncMock(), User(telegram_id=1, language='ru')))
    assert '&lt;b&gt;name&lt;/b&gt;' in text
    assert 'Ваше место: 6' in text


def test_unverified_users_can_find_profiles_and_receive_ratings(monkeypatch):
    from bot.handlers import rating
    from services.feed_service import get_next_profile
    import services.geo_service as geo
    import services.app_settings_service as app_settings
    monkeypatch.setattr(geo, 'ensure_user_geo', AsyncMock())
    monkeypatch.setattr(geo, 'hydrate_missing_user_geo', AsyncMock(return_value=0))
    monkeypatch.setattr(app_settings, 'get_setting_bool', AsyncMock(return_value=False))
    monkeypatch.setattr(rating, 'edit_or_send', AsyncMock())
    async def check(session):
        viewer = User(telegram_id=1, profile_completed=True, verified=False)
        target = User(telegram_id=2, profile_completed=True, verified=False, goal=None)
        session.add_all([viewer, target])
        await session.flush()
        assert (await get_next_profile(session, viewer)).id == target.id
        callback = AsyncMock()
        callback.data = f'rate:stars:{target.id}:5'
        await rating.rate_stars(callback, viewer, session, AsyncMock())
        assert target.rating_count == 1 and target.rating_avg == 5
        assert target.verified is False
    asyncio.run(with_database(check))


def test_goal_can_be_added_after_registration(monkeypatch):
    from bot.handlers import goals
    monkeypatch.setattr(goals, 'cleanup_user_and_prompt', AsyncMock())
    monkeypatch.setattr(goals, 'show_goal', AsyncMock())
    async def check(session):
        user = User(telegram_id=1, profile_completed=True, verified=False, goal=None)
        session.add(user)
        await session.flush()
        message = AsyncMock()
        message.text = '500'
        state = AsyncMock()
        state.get_data.return_value = {'goal_title': 'Travel'}
        await goals.goal_change_amount(message, state, user, session, AsyncMock())
        assert user.goal.title == 'Travel' and user.goal.target_sparks == 500
    asyncio.run(with_database(check))


def test_admin_leaderboard_bonus_validation_and_ranking():
    from fastapi import HTTPException
    from pydantic import ValidationError
    from api.main import ReferralLeaderboardAdjustment, adjust_referral_leaderboard, admin_referrals
    for value in [-1, 1.5, 1000001]:
        with pytest.raises(ValidationError):
            ReferralLeaderboardAdjustment(telegram_id=1, bonus=value)
    async def check(session):
        user = User(telegram_id=1, profile_completed=True, goal=None)
        session.add(user)
        await session.flush()
        await adjust_referral_leaderboard(ReferralLeaderboardAdjustment(telegram_id=1, bonus=10), session, None)
        rows = await admin_referrals(session, None)
        assert rows[0]['rank'] == 1 and rows[0]['leaderboard_count'] == 10
        assert rows[0]['referral_count'] == 0 and rows[0]['leaderboard_bonus'] == 10
        with pytest.raises(HTTPException) as error:
            await adjust_referral_leaderboard(ReferralLeaderboardAdjustment(telegram_id=999, bonus=1), session, None)
        assert error.value.status_code == 404
    asyncio.run(with_database(check))


def test_migration_recalculates_legacy_referrals():
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine, text
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1] / 'alembic/versions/007_referral_leaderboard.py'
    spec = importlib.util.spec_from_file_location('migration_007', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine('sqlite://')
    try:
        with engine.begin() as conn:
            conn.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY, verified BOOLEAN, profile_completed BOOLEAN, referral_count INTEGER)'))
            conn.execute(text('CREATE TABLE referrals (id INTEGER PRIMARY KEY, referrer_id INTEGER, referred_id INTEGER, counted_at TEXT)'))
            conn.execute(text('INSERT INTO users VALUES (1, 0, 1, 99), (2, 1, 1, 0), (3, 0, 1, 0), (4, 1, 0, 0)'))
            conn.execute(text("INSERT INTO referrals VALUES (1, 1, 2, 'old'), (2, 1, 3, 'old'), (3, 1, 4, 'old')"))
            with Operations.context(MigrationContext.configure(conn)):
                migration.upgrade()
            assert conn.scalar(text('SELECT referral_count FROM users WHERE id = 1')) == 1
            assert conn.scalar(text('SELECT referral_leaderboard_bonus FROM users WHERE id = 1')) == 0
            assert list(conn.execute(text('SELECT counted_at FROM referrals ORDER BY id')).scalars()) == ['old', None, None]
    finally:
        engine.dispose()


def test_referral_link_cannot_be_reassigned_or_counted_twice(monkeypatch):
    from bot.handlers import registration
    monkeypatch.setattr(registration, 'record_blogger_view', AsyncMock())
    monkeypatch.setattr(registration, 'clear_reply_menu_tracking', AsyncMock())
    monkeypatch.setattr(registration, 'replace_ui', AsyncMock())
    async def check(session):
        first = User(telegram_id=1, profile_completed=True, referral_code='first')
        second = User(telegram_id=2, profile_completed=True, referral_code='second')
        invited = User(telegram_id=3, profile_completed=False)
        session.add_all([first, second, invited])
        await session.flush()
        message = AsyncMock()
        message.text = '/start ref_first'
        await registration.cmd_start(message, AsyncMock(), session, invited, AsyncMock())
        await registration.cmd_start(message, AsyncMock(), session, invited, AsyncMock())
        message.text = '/start ref_second'
        await registration.cmd_start(message, AsyncMock(), session, invited, AsyncMock())
        assert invited.referred_by_id == first.id
        assert await session.scalar(select(func.count(Referral.id))) == 1
        assert await count_completed_referrals(session, first.id) == 0
    asyncio.run(with_database(check))
