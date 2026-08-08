"""Общий dual-input города: геолокация / текст + подтверждение."""

from __future__ import annotations

from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from redis.asyncio import Redis

from bot.keyboards.keyboards import city_confirm_kb, city_input_kb
from bot.texts.i18n import lang_of, t
from bot.texts.ui_labels import tx
from bot.utils.messaging import replace_ui, send_ui
from models import User
from services.geo_service import (
    GEO_SOURCE_CITY_CENTER,
    GEO_SOURCE_LOCATION,
    enqueue_regeocode,
    geocode_city,
    reverse_geocode,
)

# Контексты: registration | profile | event_create | event_edit
GEO_CTX_REG = "registration"
GEO_CTX_PROFILE = "profile"
GEO_CTX_EVENT = "event_create"
GEO_CTX_EVENT_EDIT = "event_edit"


async def ask_city(
    message: Message,
    user: User,
    state: FSMContext,
    redis: Redis | None,
    *,
    prompt_key: str = "REG_PRIVACY_CITY",
    use_tx: bool = False,
    show_my_city: bool = False,
    context: str = GEO_CTX_REG,
) -> Message:
    """Показать промпт города с кнопкой геолокации."""
    await state.update_data(geo_context=context)
    lang = lang_of(user)
    text = tx(user, prompt_key) if use_tx else t(user, prompt_key)
    kb = city_input_kb(lang, show_my_city=show_my_city and bool(user.city))
    return await replace_ui(message, text, reply_markup=kb, redis=redis)


async def process_city_location(
    message: Message,
    user: User,
    state: FSMContext,
    redis: Redis,
    *,
    confirm_state,
) -> None:
    loc = message.location
    if not loc:
        return
    result = await reverse_geocode(loc.latitude, loc.longitude, redis)
    if not result:
        # Сохраняем coords без названия — попросим текст
        await state.update_data(
            pending_lat=loc.latitude,
            pending_lon=loc.longitude,
            pending_geo_source=GEO_SOURCE_LOCATION,
            pending_city=None,
        )
        await send_ui(
            message,
            t(user, "GEO_REVERSE_FAIL"),
            reply_markup=city_input_kb(lang_of(user)),
            redis=redis,
        )
        return

    await state.update_data(
        pending_city=result.city,
        pending_lat=result.latitude,
        pending_lon=result.longitude,
        pending_geo_source=GEO_SOURCE_LOCATION,
    )
    await state.set_state(confirm_state)
    await send_ui(
        message,
        t(user, "GEO_CONFIRM_LOCATION", city=result.city),
        reply_markup=ReplyKeyboardRemove(),
        redis=redis,
        parse_mode="HTML",
    )
    # confirm buttons отдельным сообщением с inline
    await message.answer(
        t(user, "GEO_CONFIRM_HINT"),
        reply_markup=city_confirm_kb(lang_of(user)),
    )


async def process_city_text(
    message: Message,
    user: User,
    state: FSMContext,
    redis: Redis,
    *,
    confirm_state,
    allow_my_city: bool = False,
) -> None:
    raw = (message.text or "").strip()
    if not raw:
        return

    # Кнопка «мой город»
    if allow_my_city and raw == t(user, "BTN_MY_CITY") and user.city:
        await state.update_data(
            pending_city=user.city,
            pending_lat=user.latitude,
            pending_lon=user.longitude,
            pending_geo_source=user.geo_source or GEO_SOURCE_CITY_CENTER,
        )
        await state.set_state(confirm_state)
        await send_ui(
            message,
            t(user, "GEO_CONFIRM_CITY", city=user.city),
            reply_markup=ReplyKeyboardRemove(),
            redis=redis,
            parse_mode="HTML",
        )
        await message.answer(
            t(user, "GEO_CONFIRM_HINT"),
            reply_markup=city_confirm_kb(lang_of(user)),
        )
        return

    city_name = raw[:255]
    # Если уже есть pending coords от reverse fail — привяжем имя
    data = await state.get_data()
    pending_lat = data.get("pending_lat")
    pending_lon = data.get("pending_lon")
    pending_source = data.get("pending_geo_source")

    if pending_lat is not None and pending_lon is not None and pending_source == GEO_SOURCE_LOCATION and not data.get("pending_city"):
        await state.update_data(pending_city=city_name)
        await state.set_state(confirm_state)
        await send_ui(
            message,
            t(user, "GEO_CONFIRM_LOCATION", city=city_name),
            reply_markup=ReplyKeyboardRemove(),
            redis=redis,
            parse_mode="HTML",
        )
        await message.answer(
            t(user, "GEO_CONFIRM_HINT"),
            reply_markup=city_confirm_kb(lang_of(user)),
        )
        return

    result = await geocode_city(city_name, redis)
    if result:
        await state.update_data(
            pending_city=result.city,
            pending_lat=result.latitude,
            pending_lon=result.longitude,
            pending_geo_source=GEO_SOURCE_CITY_CENTER,
        )
        await state.set_state(confirm_state)
        await send_ui(
            message,
            t(user, "GEO_CONFIRM_CITY", city=result.city),
            reply_markup=ReplyKeyboardRemove(),
            redis=redis,
            parse_mode="HTML",
        )
        await message.answer(
            t(user, "GEO_CONFIRM_HINT"),
            reply_markup=city_confirm_kb(lang_of(user)),
        )
        return

    # Geocode fail — сохраняем как есть без coords
    await state.update_data(
        pending_city=city_name,
        pending_lat=None,
        pending_lon=None,
        pending_geo_source=None,
        geo_needs_regeocode=True,
    )
    await state.set_state(confirm_state)
    await send_ui(
        message,
        t(user, "GEO_CONFIRM_NO_COORDS", city=city_name),
        reply_markup=ReplyKeyboardRemove(),
        redis=redis,
        parse_mode="HTML",
    )
    await message.answer(
        t(user, "GEO_CONFIRM_HINT"),
        reply_markup=city_confirm_kb(lang_of(user)),
    )


def pending_geo_payload(data: dict) -> dict:
    return {
        "city": (data.get("pending_city") or "")[:255],
        "latitude": data.get("pending_lat"),
        "longitude": data.get("pending_lon"),
        "geo_source": data.get("pending_geo_source"),
        "needs_regeocode": bool(data.get("geo_needs_regeocode")),
    }


async def maybe_enqueue_regeocode(entity_type: str, entity_id: int, needs: bool) -> None:
    if needs and entity_id:
        await enqueue_regeocode(entity_type, entity_id)
