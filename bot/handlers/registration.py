"""Обработчики регистрации."""

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.keyboards import (
    contact_kb,
    gender_kb,
    language_kb,
    limited_menu_kb,
    next_step_kb,
    seeking_kb,
    visible_kb,
)
from bot.states.states import Registration
from bot.texts.formatters import format_own_profile
from bot.texts.i18n import (
    GENDER_BUTTONS,
    LANG_LABELS,
    SEEKING_BUTTONS,
    VISIBLE_BUTTONS,
    lang_of,
    normalize_lang,
    t,
)
from bot.texts.ui_labels import tx
from bot.utils.messaging import replace_ui, safe_delete, send_ui
from config import get_settings
from models import Goal, Referral, User
from services.blogger_service import record_blogger_view
from services.luma_ai_service import moderate_text
from services.referral_service import process_referral_on_profile_complete

router = Router()
settings = get_settings()

LANG_BY_LABEL = {v: k for k, v in LANG_LABELS.items()}


async def _send_profile_preview(message: Message, user: User, redis: Redis | None = None) -> None:
    text = f"{t(user, 'REG_PREVIEW_HEADER')}\n\n{format_own_profile(user)}"
    await replace_ui(
        message,
        text,
        photo_file_id=user.photo_file_id,
        reply_markup=next_step_kb(lang_of(user)),
        redis=redis,
    )


@router.message(CommandStart())
async def cmd_start(
    message: Message, state: FSMContext, session: AsyncSession, user: User, redis: Redis
) -> None:
    await state.clear()
    await safe_delete(message)
    args = message.text.split(maxsplit=1) if message.text else []
    payload = args[1].strip() if len(args) > 1 else ""

    if payload.startswith("ref_"):
        code = payload.replace("ref_", "", 1)
        result = await session.execute(select(User).where(User.referral_code == code))
        ref_user = result.scalar_one_or_none()
        if ref_user and ref_user.id != user.id:
            user.referred_by_id = ref_user.id
            session.add(Referral(referrer_id=ref_user.id, referred_id=user.id))
            await record_blogger_view(session, ref_user)

    if payload.startswith("event_") and user.profile_completed:
        from bot.handlers.events import open_event_by_id
        from bot.handlers.menu import send_menu

        await send_menu(message, user, redis=redis, replace=True)
        try:
            event_id = int(payload.replace("event_", "", 1))
        except ValueError:
            await send_ui(message, t(user, "EVENT_NOT_FOUND"), redis=redis)
            return
        await open_event_by_id(message, session, event_id, lang=lang_of(user), redis=redis)
        return

    if payload.startswith("evgroup_") and user.profile_completed:
        from bot.handlers.menu import send_menu

        await send_menu(message, user, redis=redis, replace=True)
        await send_ui(
            message,
            tx(user, "EVGROUP_HINT"),
            redis=redis,
        )
        return

    if user.profile_completed:
        from bot.handlers.menu import send_menu

        await send_menu(message, user, redis=redis, replace=True)
        return

    if payload.startswith("event_"):
        try:
            await state.update_data(pending_event_id=int(payload.replace("event_", "", 1)))
        except ValueError:
            pass

    await state.set_state(Registration.language)
    await replace_ui(message, t("ru", "REG_ASK_LANG"), reply_markup=language_kb(), redis=redis)


@router.message(Registration.language, F.text.in_(LANG_BY_LABEL.keys()))
async def reg_language(message: Message, state: FSMContext, user: User, session: AsyncSession, redis: Redis) -> None:
    user.language = LANG_BY_LABEL[message.text]
    await state.set_state(Registration.name)
    await safe_delete(message)
    from services.app_settings_service import get_setting_value

    rules = await get_setting_value(session, "rules_link_1")
    await replace_ui(
        message,
        t(user, "REG_RULES", rules=rules),
        reply_markup=ReplyKeyboardRemove(),
        redis=redis,
        parse_mode="HTML",
    )


@router.message(Registration.name, F.text)
async def reg_name(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
    user.display_name = message.text.strip()[:100]
    await state.set_state(Registration.photo)
    await safe_delete(message)
    await replace_ui(message, t(user, "REG_ASK_PHOTO", name=user.display_name), redis=redis)


@router.message(Registration.photo, F.photo)
async def reg_photo(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
    user.photo_file_id = message.photo[-1].file_id
    await state.set_state(Registration.gender)
    await safe_delete(message)
    await replace_ui(message, t(user, "REG_ASK_GENDER"), reply_markup=gender_kb(lang_of(user)), redis=redis)


@router.message(Registration.gender, F.text)
async def reg_gender(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
    mapping = GENDER_BUTTONS[normalize_lang(lang_of(user))]
    if message.text not in mapping:
        return
    user.gender = mapping[message.text]
    await state.set_state(Registration.seeking)
    await safe_delete(message)
    await replace_ui(message, t(user, "REG_ASK_SEEKING"), reply_markup=seeking_kb(lang_of(user)), redis=redis)


@router.message(Registration.seeking, F.text)
async def reg_seeking(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
    mapping = SEEKING_BUTTONS[normalize_lang(lang_of(user))]
    if message.text not in mapping:
        return
    user.seeking = mapping[message.text]
    await state.set_state(Registration.visible_to)
    await safe_delete(message)
    await replace_ui(message, t(user, "REG_ASK_VISIBLE"), reply_markup=visible_kb(lang_of(user)), redis=redis)


@router.message(Registration.visible_to, F.text)
async def reg_visible(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
    mapping = VISIBLE_BUTTONS[normalize_lang(lang_of(user))]
    if message.text not in mapping:
        return
    user.visible_to = mapping[message.text]
    await state.set_state(Registration.contact)
    await safe_delete(message)
    await replace_ui(message, t(user, "REG_ASK_CONTACT"), reply_markup=contact_kb(lang_of(user)), redis=redis)


@router.message(Registration.contact, F.contact)
async def reg_contact(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
    user.contact_phone = message.contact.phone_number
    await state.set_state(Registration.age)
    await safe_delete(message)
    await replace_ui(message, t(user, "REG_ASK_AGE"), reply_markup=ReplyKeyboardRemove(), redis=redis)


@router.message(Registration.age, F.text)
async def reg_age(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
    if not message.text.isdigit() or int(message.text) < 18:
        await message.answer(t(user, "ERR_AGE"))
        return
    user.age = int(message.text)
    await state.set_state(Registration.city)
    await safe_delete(message)
    await replace_ui(message, t(user, "REG_PRIVACY_CITY"), redis=redis)


@router.message(Registration.city, F.text)
async def reg_city(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
    user.city = message.text.strip()[:255]
    await state.set_state(Registration.bio)
    await safe_delete(message)
    await replace_ui(message, t(user, "REG_ASK_BIO"), redis=redis)


@router.message(Registration.bio, F.text)
async def reg_bio(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
    ok, reason = await moderate_text(message.text)
    if not ok:
        await message.answer(t(user, "MODERATION_BLOCKED", reason=reason))
        return
    user.bio = message.text.strip()[:1000]
    await state.set_state(Registration.goal_title)
    await safe_delete(message)
    await replace_ui(message, t(user, "REG_ASK_GOAL"), redis=redis)


@router.message(Registration.goal_title, F.text)
async def reg_goal_title(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
    await state.update_data(goal_title=message.text.strip()[:255])
    await state.set_state(Registration.goal_amount)
    await safe_delete(message)
    await replace_ui(message, t(user, "REG_ASK_GOAL_AMOUNT"), redis=redis)


@router.message(Registration.goal_amount, F.text)
async def reg_goal_amount(
    message: Message, state: FSMContext, user: User, session: AsyncSession, redis: Redis
) -> None:
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer(t(user, "ERR_INVALID_INPUT"))
        return
    data = await state.get_data()
    goal = Goal(user_id=user.id, title=data["goal_title"], target_sparks=int(message.text))
    session.add(goal)
    await session.flush()
    await session.refresh(user, ["goal"])
    await state.set_state(Registration.preview)
    await safe_delete(message)
    await _send_profile_preview(message, user, redis=redis)


@router.callback_query(Registration.preview, F.data == "reg:next")
async def reg_finish(
    callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession, redis: Redis
) -> None:
    data = await state.get_data()
    pending_event_id = data.get("pending_event_id")
    user.profile_completed = True
    await process_referral_on_profile_complete(session, user)
    await state.clear()
    await safe_delete(callback.message)
    await replace_ui(
        callback.message,
        t(user, "REG_COMPLETE"),
        reply_markup=limited_menu_kb(lang_of(user)),
        redis=redis,
    )
    if pending_event_id:
        from bot.handlers.events import open_event_by_id

        await open_event_by_id(callback.message, session, int(pending_event_id), lang=lang_of(user), redis=redis)
    await callback.answer()
