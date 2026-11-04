"""Раздел Оценивать."""

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import logging

from bot.keyboards.keyboards import (
    complaint_reasons_kb,
    like_inbox_done_kb,
    match_dm_kb,
    rate_after_stars_kb,
    rate_card_kb,
    support_type_kb,
)

logger = logging.getLogger(__name__)
from bot.states.states import RatingFlow
from bot.texts.formatters import format_other_profile
from bot.texts.i18n import complaint_reason_label, lang_of, t
from bot.texts.ui_labels import service_err
from bot.utils.messaging import (
    cleanup_user_and_prompt,
    edit_or_send,
    safe_edit_text,
    send_profile_media_chat,
    strip_inline_keyboard,
)
from models import Complaint, Like, Rating, User
from services.feed_service import (
    clear_profile_skips_for_user,
    get_next_profile,
    mark_feed_exhausted,
    recalculate_rating,
    record_profile_skip,
)
from services.like_inbox_service import (
    clear_inbox_message,
    get_next_unseen_like,
    is_inbox_browsing,
    mark_like_seen,
    mark_like_seen_from_user,
    notify_like_batch_if_needed,
    set_inbox_browsing,
)
from services.match_service import check_mutual_like
from services.profile_media import get_profile_media
from services.sparks_service import support_goal
from services.user_service import get_user_by_id

router = Router()


def user_dm_url(user: User) -> str:
    if user.username:
        return f"https://t.me/{user.username}"
    return f"tg://user?id={user.telegram_id}"


async def send_user_card(
    bot: Bot,
    chat_id: int,
    profile: User,
    *,
    prefix: str = "",
    reply_markup=None,
    lang: str = "ru",
    viewer: User | None = None,
) -> None:
    text = format_other_profile(profile, lang, viewer=viewer)
    if prefix:
        text = f"{prefix}\n\n{text}"
    await send_profile_media_chat(
        bot, chat_id, text, get_profile_media(profile), reply_markup=reply_markup
    )


async def notify_match(bot: Bot, recipient: User, other: User) -> None:
    text = t(recipient, "MATCH_MSG", name=other.display_name)
    kb = match_dm_kb(user_dm_url(other), lang_of(recipient))
    try:
        await bot.send_message(recipient.telegram_id, text, reply_markup=kb)
    except Exception:
        pass


async def notify_incoming_like(
    bot: Bot,
    target: User,
    from_user: User,
    *,
    comment: str | None = None,
    session: AsyncSession | None = None,
    redis: Redis | None = None,
) -> None:
    """Пакетные уведомления с порогом 3; одиночные мгновенные больше не шлём."""
    del from_user, comment  # комментарий остаётся на Like и виден при просмотре inbox
    if session is None:
        return
    await notify_like_batch_if_needed(bot, session, target, redis=redis)


async def show_like_inbox_done(message: Message, user: User, *, redis: Redis | None = None) -> None:
    await set_inbox_browsing(redis, user.id, False)
    await clear_inbox_message(redis, user.id)
    await edit_or_send(
        message,
        t(user, "LIKE_INBOX_DONE"),
        reply_markup=like_inbox_done_kb(lang_of(user)),
        redis=redis,
        edit=False,
        track=True,
        keep_previous=True,
    )


async def show_next_inbox_profile(
    message: Message,
    user: User,
    session: AsyncSession,
    *,
    redis: Redis | None = None,
    edit: bool = True,
    finalize_previous: bool = False,
) -> None:
    if finalize_previous and message.from_user and message.from_user.is_bot:
        await strip_inline_keyboard(message)

    like = await get_next_unseen_like(session, user.id)
    if not like:
        await show_like_inbox_done(message, user, redis=redis)
        return

    profile = await get_user_by_id(session, like.from_user_id)
    if not profile:
        await mark_like_seen(session, like)
        await session.commit()
        await show_next_inbox_profile(
            message, user, session, redis=redis, edit=edit, finalize_previous=False
        )
        return

    await mark_like_seen(session, like)
    await session.commit()
    await set_inbox_browsing(redis, user.id, True)

    text = format_other_profile(profile, lang_of(user), viewer=user)
    if like.comment:
        text = f"{t(user, 'LIKE_COMMENT_NOTIFY', comment=like.comment)}\n\n{text}"
    await edit_or_send(
        message,
        text,
        media=get_profile_media(profile),
        reply_markup=rate_card_kb(profile.id, lang_of(user)),
        redis=redis,
        edit=False,
        track=True,
        keep_previous=True,
        finalize_previous=finalize_previous or bool(edit),
    )


async def _after_rate_action(
    message: Message,
    user: User,
    session: AsyncSession,
    exclude_id: int,
    *,
    redis: Redis | None = None,
) -> None:
    """После лайка/скипа: продолжить inbox или обычную ленту."""
    if await is_inbox_browsing(redis, user.id):
        await mark_like_seen_from_user(session, to_user_id=user.id, from_user_id=exclude_id)
        await session.commit()
        await show_next_inbox_profile(
            message, user, session, redis=redis, edit=False, finalize_previous=True
        )
        return
    await show_next_profile(
        message, user, session, [exclude_id], redis=redis, edit=False, finalize_previous=True
    )


async def show_next_profile(
    message: Message,
    user: User,
    session: AsyncSession,
    exclude: list[int] | None = None,
    *,
    redis: Redis | None = None,
    edit: bool = False,
    finalize_previous: bool = False,
    allow_feed_reset: bool = False,
) -> None:
    from bot.handlers.luma import try_show_next_luma_person

    if finalize_previous and message.from_user and message.from_user.is_bot:
        await strip_inline_keyboard(message)

    if await try_show_next_luma_person(
        message, user, session, redis, exclude, edit=edit, finalize_previous=finalize_previous
    ):
        return

    target = await get_next_profile(session, user, exclude or [], redis=redis)
    if not target and allow_feed_reset:
        # Вход из меню «Оценивать»: скипы накопились — новый круг без ожидания ночного cron
        cleared = await clear_profile_skips_for_user(session, user.id)
        user.feed_exhausted = False
        await session.commit()
        logger.info(
            "rate feed reset telegram_id=%s cleared_skips=%s seeking=%s city=%s",
            user.telegram_id,
            cleared,
            user.seeking,
            user.city,
        )
        target = await get_next_profile(session, user, exclude or [], redis=redis)
    if not target:
        mark_feed_exhausted(user)
        logger.info(
            "rate feed empty telegram_id=%s user_id=%s seeking=%s city=%s feed_exhausted=%s",
            user.telegram_id,
            user.id,
            user.seeking,
            user.city,
            user.feed_exhausted,
        )
        await edit_or_send(
            message,
            t(user, "RATE_EMPTY"),
            redis=redis,
            edit=False,
            track=True,
            keep_previous=True,
            finalize_previous=finalize_previous,
        )
        return
    from services.event_service import sync_events_organized

    await sync_events_organized(session, target)
    text = format_other_profile(target, lang_of(user), viewer=user)
    kb = rate_card_kb(target.id, lang_of(user))
    await edit_or_send(
        message,
        text,
        media=get_profile_media(target),
        reply_markup=kb,
        redis=redis,
        edit=False,
        track=True,
        keep_previous=True,
        finalize_previous=finalize_previous,
    )


async def _create_like_if_needed(session: AsyncSession, from_id: int, to_id: int, comment: str | None = None) -> bool:
    existing = await session.execute(
        select(Like).where(Like.from_user_id == from_id, Like.to_user_id == to_id)
    )
    like = existing.scalar_one_or_none()
    if like:
        if comment and not like.comment:
            like.comment = comment
        return False
    session.add(Like(from_user_id=from_id, to_user_id=to_id, comment=comment))
    await session.flush()
    return True


@router.callback_query(F.data.startswith("rate:skip:"))
async def rate_skip(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
    """Пропуск анкеты — больше не показывать в «Оценивать»."""
    target_id = int(callback.data.rsplit(":", 1)[-1])
    target = await get_user_by_id(session, target_id)
    if not target:
        await callback.answer(t(user, "RATE_NOT_FOUND"))
        return

    await record_profile_skip(session, user.id, target_id)
    # Фиксируем сразу, чтобы пропуск не потерялся при ошибке дальше
    await session.commit()

    await _after_rate_action(callback.message, user, session, target_id, redis=redis)
    await callback.answer()


@router.callback_query(F.data.startswith("rate:like:"))
async def rate_like(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
    target_id = int(callback.data.rsplit(":", 1)[-1])
    target = await get_user_by_id(session, target_id)
    if not target:
        await callback.answer(t(user, "RATE_NOT_FOUND"))
        return

    is_new = await _create_like_if_needed(session, user.id, target_id)
    # Скип — чтобы анкета не вернулась до суточного сброса (лайк в БД остаётся)
    await record_profile_skip(session, user.id, target_id)
    if is_new and await check_mutual_like(session, user, target):
        await notify_match(callback.bot, user, target)
        await notify_match(callback.bot, target, user)
    elif is_new:
        await notify_incoming_like(callback.bot, target, user, session=session, redis=redis)

    await _after_rate_action(callback.message, user, session, target_id, redis=redis)
    await callback.answer()


@router.callback_query(F.data == "like:view_inbox")
async def like_view_inbox(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
    await clear_inbox_message(redis, user.id)
    await show_next_inbox_profile(
        callback.message, user, session, redis=redis, edit=True, finalize_previous=False
    )
    await callback.answer()


@router.callback_query(F.data == "like:inbox_rate")
async def like_inbox_rate(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
    await set_inbox_browsing(redis, user.id, False)
    await show_next_profile(
        callback.message, user, session, redis=redis, edit=True, finalize_previous=False
    )
    await callback.answer()


@router.callback_query(F.data.startswith("like:view:"))
async def like_view_profile(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
    from_user_id = int(callback.data.split(":")[-1])
    profile = await get_user_by_id(session, from_user_id)
    if not profile:
        await callback.answer(t(user, "RATE_NOT_FOUND"), show_alert=True)
        return
    await mark_like_seen_from_user(session, to_user_id=user.id, from_user_id=from_user_id)
    await session.commit()
    text = format_other_profile(profile, lang_of(user), viewer=user)
    await edit_or_send(
        callback.message,
        text,
        media=get_profile_media(profile),
        reply_markup=rate_card_kb(profile.id, lang_of(user)),
        redis=redis,
        edit=True,
    )
    await callback.answer()


@router.callback_query(F.data == "like:decline")
async def like_decline(callback: CallbackQuery, user: User, redis: Redis) -> None:
    await set_inbox_browsing(redis, user.id, False)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer(t(user, "LIKE_VIEW_DECLINED"))


@router.callback_query(F.data.startswith("rate:comment:"))
async def rate_comment_start(callback: CallbackQuery, state: FSMContext, user: User, redis: Redis) -> None:
    target_id = int(callback.data.split(":")[-1])
    await state.set_state(RatingFlow.comment)
    prompt = await safe_edit_text(callback.message, t(user, "RATE_COMMENT_HINT"), redis=redis)
    await state.update_data(
        target_id=target_id,
        prompt_message_id=prompt.message_id if prompt else callback.message.message_id,
    )
    await callback.answer()


@router.message(RatingFlow.comment, F.text)
async def rate_comment_save(
    message: Message, state: FSMContext, user: User, session: AsyncSession, redis: Redis
) -> None:
    data = await state.get_data()
    target_id = data["target_id"]
    target = await get_user_by_id(session, target_id)
    prompt_id = data.get("prompt_message_id")
    if not target:
        await state.clear()
        await cleanup_user_and_prompt(message, prompt_message_id=prompt_id)
        return

    is_new = await _create_like_if_needed(session, user.id, target_id, comment=message.text)
    # Скип — чтобы анкета не вернулась до суточного сброса (лайк в БД остаётся)
    await record_profile_skip(session, user.id, target_id)
    if is_new and await check_mutual_like(session, user, target):
        await notify_match(message.bot, user, target)
        await notify_match(message.bot, target, user)
        try:
            await message.bot.send_message(
                target.telegram_id,
                t(target, "LIKE_COMMENT_ON_MATCH", comment=message.text),
            )
        except Exception:
            pass
    elif is_new:
        await notify_incoming_like(
            message.bot, target, user, comment=message.text, session=session, redis=redis
        )
    else:
        # Комментарий к уже существующему лайку — тоже через batch-порог
        await notify_incoming_like(
            message.bot, target, user, comment=message.text, session=session, redis=redis
        )

    await state.clear()
    await cleanup_user_and_prompt(message, prompt_message_id=prompt_id)
    await _after_rate_action(message, user, session, target_id, redis=redis)


@router.callback_query(F.data.startswith("rate:stars:"))
async def rate_stars(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
    """После оценки 1–5 ТЗ требует ещё одно действие — не переключаем анкету сразу."""
    parts = callback.data.split(":")
    target_id, stars = int(parts[2]), int(parts[3])
    existing = await session.execute(
        select(Rating).where(Rating.from_user_id == user.id, Rating.to_user_id == target_id)
    )
    rating = existing.scalar_one_or_none()
    if rating:
        rating.stars = stars
    else:
        session.add(Rating(from_user_id=user.id, to_user_id=target_id, stars=stars))
    await recalculate_rating(session, target_id)
    await callback.answer(t(user, "RATE_STARS_DONE", stars=stars))
    target = await get_user_by_id(session, target_id)
    text = format_other_profile(target, lang_of(user), viewer=user) if target else t(user, "RATE_AFTER_STARS")
    text = f"{text}\n\n{t(user, 'RATE_AFTER_STARS')}"
    await edit_or_send(
        callback.message,
        text,
        media=get_profile_media(target) if target else [],
        reply_markup=rate_after_stars_kb(target_id, lang_of(user)),
        redis=redis,
        edit=True,
    )


@router.callback_query(F.data.startswith("rate:support:"))
async def rate_support_start(callback: CallbackQuery, user: User, redis: Redis) -> None:
    target_id = int(callback.data.split(":")[-1])
    await safe_edit_text(
        callback.message,
        t(user, "RATE_SUPPORT_HINT"),
        reply_markup=support_type_kb(target_id, lang_of(user)),
        redis=redis,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rate:sup:"))
async def rate_support_type(callback: CallbackQuery, state: FSMContext, user: User, redis: Redis) -> None:
    parts = callback.data.split(":")
    anon = parts[2] == "anon"
    target_id = int(parts[3])
    await state.set_state(RatingFlow.support_amount)
    prompt = await safe_edit_text(callback.message, t(user, "RATE_SUPPORT_AMOUNT"), redis=redis)
    await state.update_data(
        target_id=target_id,
        anonymous=anon,
        prompt_message_id=prompt.message_id if prompt else callback.message.message_id,
    )
    await callback.answer()


@router.message(RatingFlow.support_amount, F.text)
async def rate_support_amount(
    message: Message, state: FSMContext, user: User, session: AsyncSession, redis: Redis
) -> None:
    data = await state.get_data()
    prompt_id = data.get("prompt_message_id")
    if not message.text.isdigit():
        await message.answer(t(user, "ERR_INVALID_INPUT"))
        return
    amount = int(message.text)
    if amount < 10 or amount > 500000:
        await message.answer(t(user, "RATE_SUPPORT_AMOUNT_RANGE"))
        return
    target = await get_user_by_id(session, data["target_id"])
    if not target:
        await state.clear()
        await cleanup_user_and_prompt(message, prompt_message_id=prompt_id)
        return
    anonymous = bool(data["anonymous"])
    try:
        await support_goal(session, user, target, amount, anonymous)
    except ValueError as e:
        # Не скипаем анкету: при нехватке искр оставляем ввод суммы,
        # чтобы после пополнения можно было сразу повторить.
        await message.answer(service_err(user, e))
        return

    try:
        if anonymous:
            await message.bot.send_message(
                target.telegram_id,
                t(target, "RATE_SUPPORT_NOTIFY_ANON", amount=amount),
            )
        else:
            await send_user_card(
                message.bot,
                target.telegram_id,
                user,
                prefix=t(target, "RATE_SUPPORT_NOTIFY_OPEN", amount=amount),
                reply_markup=rate_card_kb(user.id, lang_of(target)),
                lang=lang_of(target),
                viewer=target,
            )
    except Exception:
        pass

    await state.clear()
    await cleanup_user_and_prompt(message, prompt_message_id=prompt_id)
    from services.event_service import sync_events_organized

    await sync_events_organized(session, target)
    text = (
        f"{t(user, 'RATE_SUPPORT_DONE', name=target.display_name or '—', amount=amount)}\n\n"
        f"{format_other_profile(target, lang_of(user), viewer=user)}"
    )
    await edit_or_send(
        message,
        text,
        media=get_profile_media(target),
        reply_markup=rate_card_kb(target.id, lang_of(user)),
        redis=redis,
        edit=False,
        track=True,
    )


@router.callback_query(F.data.startswith("rate:report:"))
async def rate_report_start(callback: CallbackQuery, user: User, redis: Redis) -> None:
    target_id = int(callback.data.split(":")[-1])
    await safe_edit_text(
        callback.message,
        t(user, "RATE_REPORT_ASK"),
        reply_markup=complaint_reasons_kb(target_id, kind="user", lang=lang_of(user)),
        redis=redis,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rate:reason:"))
async def rate_report_reason(
    callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis
) -> None:
    parts = callback.data.split(":")
    reason_code, target_id = parts[2], int(parts[3])
    label = complaint_reason_label(lang_of(user), reason_code)
    session.add(
        Complaint(
            reporter_id=user.id,
            target_user_id=target_id,
            complaint_type="user",
            text=f"{reason_code}: {label}",
        )
    )
    await callback.answer(t(user, "RATE_REPORT_DONE"))
    await record_profile_skip(session, user.id, target_id)
    await session.commit()
    await _after_rate_action(callback.message, user, session, target_id, redis=redis)
