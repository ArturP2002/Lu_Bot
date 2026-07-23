"""Раздел Тусовки."""

from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.keyboards import (
    app_decision_kb,
    complaint_reasons_kb,
    event_attending_kb,
    event_card_kb,
    event_categories_kb,
    event_close_confirm_kb,
    event_delete_confirm_kb,
    event_edit_fields_kb,
    event_manage_kb,
    event_participants_kb,
    event_pay_confirm_kb,
    events_menu_kb,
    invite_kb,
    my_events_list_kb,
)
from bot.states.states import EventCreate, EventEdit, EventReport
from bot.texts import messages as msg
from bot.texts.formatters import format_other_profile
from bot.texts.i18n import complaint_reason_label, lang_of, t
from bot.texts.ui_labels import category_label, lbl, localize_stored_category, service_err, tx
from bot.utils.messaging import (
    cleanup_user_and_prompt,
    safe_edit_media,
    safe_edit_text,
    send_ui,
)
from config import get_settings
from models import Complaint, Event, EventApplication, EventCategory, EventStatus, User
from models.entities import ApplicationStatus
from services.blogger_service import pay_blogger_commission
from services.event_service import (
    boost_event,
    can_create_event,
    close_event_and_invite,
    get_boost_price_for_user,
    get_next_event,
    get_pin_price_for_user,
    is_topic_category,
    pin_event,
    send_mass_invites,
    sync_events_organized,
)
from services.luma_ai_service import moderate_text
from services.sparks_service import has_paid_event_fee, pay_event_fee
from services.user_service import get_user_by_id, is_premium

router = Router()
settings = get_settings()


async def _event_manage_kb(
    session: AsyncSession,
    user: User,
    event_id: int,
    mass_available: bool,
    lang: str,
):
    event = await session.get(Event, event_id)
    boost_price = await get_boost_price_for_user(session, user, event)
    pin_price = await get_pin_price_for_user(session, user, hours=1)
    return event_manage_kb(
        event_id,
        mass_available,
        lang,
        boost_price=boost_price,
        pin_price=pin_price,
    )


def format_event_card(event: Event, organizer: User | None = None, lang: str = "ru") -> str:
    org = ""
    if organizer:
        org = f"\n👤 {organizer.display_name or organizer.username or '—'}"
    now = datetime.now(timezone.utc)
    pinned_until = event.pinned_until
    if pinned_until is not None and pinned_until.tzinfo is None:
        pinned_until = pinned_until.replace(tzinfo=timezone.utc)
    pin = " 📌" if pinned_until and pinned_until > now else ""
    boost = " ⬆️" if event.boosted_at else ""
    return tx(
        lang,
        "EVENT_CARD",
        title=event.title,
        pin=pin,
        boost=boost,
        category=localize_stored_category(event.category, lang),
        city=event.city,
        address=event.address,
        date=event.event_date,
        time=event.event_time,
        men_label=tx(lang, "EVENT_MEN"),
        men_count=event.men_count,
        men_needed=event.men_needed,
        women_label=tx(lang, "EVENT_WOMEN"),
        women_count=event.women_count,
        women_needed=event.women_needed,
        price=event.price,
        org=org,
        description=event.description or "",
    )


async def _send_application_card(
  bot,
  chat_id: int,
  applicant: User,
  app_id: int,
  *,
  prefix: str = "",
  lang: str = "ru",
) -> None:
  """Карточка заявки: фото + анкета + кнопки принять/отклонить."""
  text = format_other_profile(applicant, lang)
  if prefix:
    text = f"{prefix}\n\n{text}"
  kb = app_decision_kb(app_id, lang=lang)
  if applicant.photo_file_id:
    await bot.send_photo(chat_id, applicant.photo_file_id, caption=text, reply_markup=kb)
  else:
    await bot.send_message(chat_id, text, reply_markup=kb)


async def show_events_menu(
  message: Message,
  *,
  user: User | None = None,
  redis: Redis | None = None,
  edit: bool = False,
) -> None:
  lang = lang_of(user) if user else "ru"
  text = t(user, "EVENTS_INTRO") if user else msg.EVENTS_INTRO
  if edit:
    await safe_edit_text(message, text, reply_markup=events_menu_kb(lang), redis=redis)
  else:
    await send_ui(message, text, reply_markup=events_menu_kb(lang), redis=redis)


async def show_event_card(
  message: Message,
  event: Event,
  *,
  lang: str = "ru",
  redis: Redis | None = None,
  session: AsyncSession | None = None,
) -> None:
  """Показать карточку тусовки (по deep link или из ленты)."""
  org = None
  if session:
    org = await get_user_by_id(session, event.organizer_id)
  text = format_event_card(event, org, lang=lang)
  await send_ui(
    message,
    text,
    photo_file_id=event.photo_file_id,
    reply_markup=event_card_kb(event.id, lang),
    redis=redis,
  )


async def open_event_by_id(
  message: Message,
  session: AsyncSession,
  event_id: int,
  *,
  lang: str = "ru",
  redis: Redis | None = None,
) -> bool:
  """Открыть тусовку по ID. True — найдена и показана."""
  event = await session.get(Event, event_id)
  if not event or event.status == EventStatus.DELETED.value:
    await send_ui(message, tx(lang, "EVENT_NOT_FOUND"), redis=redis)
    return False
  if event.status == EventStatus.CLOSED.value:
    await send_ui(message, tx(lang, "EVENT_CLOSED", title=event.title), redis=redis)
    return False
  await show_event_card(message, event, lang=lang, redis=redis, session=session)
  return True


@router.callback_query(F.data == "ev:create")
async def ev_create_start(
  callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession, redis: Redis
) -> None:
  ok, err = await can_create_event(session, user)
  if not ok:
    await callback.answer(err, show_alert=True)
    return
  await state.set_state(EventCreate.title)
  prompt = await safe_edit_text(callback.message, tx(user, "EVENT_ASK_TITLE"), redis=redis)
  await state.update_data(prompt_message_id=prompt.message_id if prompt else callback.message.message_id)
  await callback.answer()


@router.message(EventCreate.title, F.text)
async def ev_create_title(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  data = await state.get_data()
  await state.update_data(title=message.text.strip()[:255])
  await state.set_state(EventCreate.city)
  await cleanup_user_and_prompt(message, prompt_message_id=data.get("prompt_message_id"))
  prompt = await send_ui(message, tx(user, "EVENT_ASK_CITY"), redis=redis)
  await state.update_data(prompt_message_id=prompt.message_id)


@router.message(EventCreate.city, F.text)
async def ev_create_city(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  data = await state.get_data()
  await state.update_data(city=message.text.strip()[:255])
  await state.set_state(EventCreate.address)
  await cleanup_user_and_prompt(message, prompt_message_id=data.get("prompt_message_id"))
  prompt = await send_ui(message, tx(user, "EVENT_ASK_ADDRESS"), redis=redis)
  await state.update_data(prompt_message_id=prompt.message_id)


@router.message(EventCreate.address, F.text)
async def ev_create_address(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  data = await state.get_data()
  await state.update_data(address=message.text.strip()[:512])
  await state.set_state(EventCreate.datetime)
  await cleanup_user_and_prompt(message, prompt_message_id=data.get("prompt_message_id"))
  prompt = await send_ui(message, tx(user, "EVENT_ASK_DATETIME"), redis=redis)
  await state.update_data(prompt_message_id=prompt.message_id)


@router.message(EventCreate.datetime, F.text)
async def ev_create_datetime(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  data = await state.get_data()
  parts = message.text.strip().split(maxsplit=1)
  await state.update_data(event_date=parts[0], event_time=parts[1] if len(parts) > 1 else "19:00")
  await state.set_state(EventCreate.price)
  await cleanup_user_and_prompt(message, prompt_message_id=data.get("prompt_message_id"))
  prompt = await send_ui(message, tx(user, "EVENT_ASK_PRICE"), redis=redis)
  await state.update_data(prompt_message_id=prompt.message_id)


@router.message(EventCreate.price, F.text)
async def ev_create_price(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  data = await state.get_data()
  await state.update_data(price=int(message.text) if message.text.isdigit() else 0)
  await state.set_state(EventCreate.men)
  await cleanup_user_and_prompt(message, prompt_message_id=data.get("prompt_message_id"))
  prompt = await send_ui(message, tx(user, "EVENT_ASK_MEN"), redis=redis)
  await state.update_data(prompt_message_id=prompt.message_id)


@router.message(EventCreate.men, F.text)
async def ev_create_men(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  data = await state.get_data()
  await state.update_data(men=int(message.text) if message.text.isdigit() else 0)
  await state.set_state(EventCreate.women)
  await cleanup_user_and_prompt(message, prompt_message_id=data.get("prompt_message_id"))
  prompt = await send_ui(message, tx(user, "EVENT_ASK_WOMEN"), redis=redis)
  await state.update_data(prompt_message_id=prompt.message_id)


@router.message(EventCreate.women, F.text)
async def ev_create_women(message: Message, state: FSMContext, user: User, session: AsyncSession, redis: Redis) -> None:
  data = await state.get_data()
  await state.update_data(women=int(message.text) if message.text.isdigit() else 0)
  await state.set_state(EventCreate.category)
  await cleanup_user_and_prompt(message, prompt_message_id=data.get("prompt_message_id"))
  result = await session.execute(select(EventCategory).where(EventCategory.is_active.is_(True)))
  cats = [c for c in result.scalars().all() if is_topic_category(c)]
  lang = lang_of(user)
  from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

  if not cats:
    await send_ui(message, tx(user, "EVENT_EMPTY_CAT"), redis=redis)
    return

  rows, row = [], []
  for c in cats:
    row.append(
      InlineKeyboardButton(
        text=category_label(c.name, lang, emoji=c.emoji or ""),
        callback_data=f"ev:createcat:{c.id}",
      )
    )
    if len(row) == 2:
      rows.append(row)
      row = []
  if row:
    rows.append(row)
  prompt = await send_ui(
    message,
    tx(user, "EVENT_ASK_CATEGORY"),
    reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    redis=redis,
  )
  await state.update_data(prompt_message_id=prompt.message_id)


@router.callback_query(EventCreate.category, F.data.startswith("ev:createcat:"))
async def ev_create_category(
  callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession, redis: Redis
) -> None:
  cat_id = int(callback.data.split(":")[-1])
  cat = await session.get(EventCategory, cat_id)
  cat_name = f"{cat.emoji} {cat.name}".strip() if cat else tx(user, "EVENT_DEFAULT_CAT")
  await state.update_data(category=cat_name)
  await state.set_state(EventCreate.photo)
  prompt = await safe_edit_text(callback.message, tx(user, "EVENT_ASK_PHOTO"), redis=redis)
  await state.update_data(prompt_message_id=prompt.message_id if prompt else callback.message.message_id)
  await callback.answer()


@router.message(EventCreate.photo, F.photo)
async def ev_create_photo(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  data = await state.get_data()
  await state.update_data(photo=message.photo[-1].file_id)
  await state.set_state(EventCreate.description)
  await cleanup_user_and_prompt(message, prompt_message_id=data.get("prompt_message_id"))
  prompt = await send_ui(message, tx(user, "EVENT_ASK_DESC"), redis=redis)
  await state.update_data(prompt_message_id=prompt.message_id)


@router.message(EventCreate.description, F.text)
async def ev_create_description(
  message: Message, state: FSMContext, user: User, session: AsyncSession, redis: Redis
) -> None:
  data = await state.get_data()
  ok, reason = await moderate_text(message.text)
  if not ok:
    await message.answer(t(user, "MODERATION_BLOCKED", reason=reason))
    return
  event = Event(
    organizer_id=user.id,
    title=data["title"],
    city=data["city"],
    address=data["address"],
    event_date=data["event_date"],
    event_time=data["event_time"],
    price=data["price"],
    men_needed=data["men"],
    women_needed=data["women"],
    photo_file_id=data.get("photo"),
    description=message.text.strip()[:2000],
    category=data.get("category"),
    status=EventStatus.ACTIVE.value,
  )
  session.add(event)
  await state.clear()
  await cleanup_user_and_prompt(message, prompt_message_id=data.get("prompt_message_id"))
  await send_ui(
    message,
    tx(user, "EVENT_CREATED", title=event.title),
    reply_markup=events_menu_kb(lang_of(user)),
    redis=redis,
  )


@router.callback_query(F.data == "ev:menu")
async def ev_menu(callback: CallbackQuery, user: User, redis: Redis) -> None:
  await show_events_menu(callback.message, user=user, redis=redis, edit=True)
  await callback.answer()


@router.callback_query(F.data == "ev:my")
async def ev_my(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  lang = lang_of(user)
  org_result = await session.execute(
    select(Event).where(Event.organizer_id == user.id, Event.status != EventStatus.DELETED.value)
  )
  organized = list(org_result.scalars().all())

  apps_result = await session.execute(
    select(EventApplication).where(
      EventApplication.user_id == user.id,
      EventApplication.status == ApplicationStatus.ACCEPTED.value,
    )
  )
  attending: list[Event] = []
  for app in apps_result.scalars().all():
    ev = await session.get(Event, app.event_id)
    if ev and ev.status != EventStatus.DELETED.value and ev.organizer_id != user.id:
      attending.append(ev)

  if not organized and not attending:
    await safe_edit_text(callback.message, tx(user, "EVENT_NONE"), reply_markup=events_menu_kb(lang), redis=redis)
    await callback.answer()
    return

  items: list[tuple[int, str]] = []
  for ev in organized:
    mark = "👑" if ev.status == EventStatus.ACTIVE.value else "🔒"
    items.append((ev.id, f"{mark} {ev.title}"))
  for ev in attending:
    mark = "✅" if ev.status == EventStatus.ACTIVE.value else "🔒"
    items.append((ev.id, f"{mark} {ev.title}"))

  await safe_edit_text(
    callback.message,
    tx(user, "EVENT_PICK"),
    reply_markup=my_events_list_kb(items, lang),
    redis=redis,
  )
  await callback.answer()


@router.callback_query(F.data.startswith("ev:pick:"))
async def ev_pick(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  lang = lang_of(user)
  event_id = int(callback.data.split(":")[-1])
  event = await session.get(Event, event_id)
  if not event or event.status == EventStatus.DELETED.value:
    await callback.answer(tx(user, "EVENT_NOT_FOUND"), show_alert=True)
    return

  mark = "🟢" if event.status == EventStatus.ACTIVE.value else "🔒"
  meta = f"{mark} «{event.title}»\n📍 {event.city} · {event.event_date} {event.event_time}"

  if event.organizer_id == user.id:
    mass_ok = is_premium(user) and event.mass_invites_used < 5
    await safe_edit_text(
      callback.message,
      tx(user, "EVENT_ROLE_ORG", meta=meta),
      reply_markup=await _event_manage_kb(session, user, event.id, mass_ok, lang),
      redis=redis,
    )
  else:
    fee_paid = await has_paid_event_fee(session, user.id, event.id) if event.price > 0 else False
    fee_line = ""
    if event.price > 0:
      fee_key = "EVENT_FEE_LINE_PAID" if fee_paid else "EVENT_FEE_LINE"
      fee_line = tx(user, fee_key, price=event.price)
    await safe_edit_text(
      callback.message,
      tx(user, "EVENT_ROLE_ATTEND", meta=meta, fee_line=fee_line),
      reply_markup=event_attending_kb(event.id, price=event.price or 0, fee_paid=fee_paid, lang=lang),
      redis=redis,
    )
  await callback.answer()


@router.callback_query(F.data.startswith("ev:open:"))
async def ev_open(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  lang = lang_of(user)
  event_id = int(callback.data.split(":")[-1])
  event = await session.get(Event, event_id)
  if not event or event.status == EventStatus.DELETED.value:
    await callback.answer(tx(user, "EVENT_NOT_FOUND"), show_alert=True)
    return
  text = format_event_card(event, lang=lang)
  await safe_edit_media(
    callback.message,
    text,
    event.photo_file_id,
    reply_markup=event_card_kb(event.id, lang),
    redis=redis,
  )
  await callback.answer()


@router.callback_query(F.data == "ev:pay:done")
async def ev_pay_done(callback: CallbackQuery, user: User) -> None:
  await callback.answer(tx(user, "EVENT_FEE_PAID"), show_alert=False)


@router.callback_query(F.data.startswith("ev:pay:yes:"))
async def ev_pay_confirm(
  callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis
) -> None:
  lang = lang_of(user)
  event_id = int(callback.data.split(":")[-1])
  event = await session.get(Event, event_id)
  if not event or event.status == EventStatus.DELETED.value:
    await callback.answer(tx(user, "EVENT_NOT_FOUND"), show_alert=True)
    return
  if not event.price or event.price <= 0:
    await callback.answer(tx(user, "EVENT_FEE_NONE"), show_alert=True)
    return

  app = await session.execute(
    select(EventApplication).where(
      EventApplication.event_id == event_id,
      EventApplication.user_id == user.id,
      EventApplication.status == ApplicationStatus.ACCEPTED.value,
    )
  )
  if not app.scalar_one_or_none():
    await callback.answer(tx(user, "EVENT_FEE_NEED_ACCEPT"), show_alert=True)
    return

  organizer = await get_user_by_id(session, event.organizer_id)
  if not organizer:
    await callback.answer(tx(user, "EVENT_ORG_MISSING"), show_alert=True)
    return

  try:
    await pay_event_fee(session, user, organizer, event.id, event.price)
  except ValueError as e:
    await callback.answer(service_err(user, e), show_alert=True)
    return

  try:
    await callback.bot.send_message(
      organizer.telegram_id,
      tx(
        organizer,
        "EVENT_FEE_PAID_NOTIFY",
        name=user.display_name,
        price=event.price,
        title=event.title,
      ),
    )
  except Exception:
    pass

  meta = f"🟢 «{event.title}»\n📍 {event.city} · {event.event_date} {event.event_time}"
  fee_line = tx(user, "EVENT_FEE_LINE_PAID", price=event.price)
  await safe_edit_text(
    callback.message,
    tx(user, "EVENT_ROLE_ATTEND", meta=meta, fee_line=fee_line),
    reply_markup=event_attending_kb(event.id, price=event.price, fee_paid=True, lang=lang),
    redis=redis,
  )
  await callback.answer(tx(user, "EVENT_FEE_DONE"), show_alert=False)


@router.callback_query(F.data.startswith("ev:pay:"))
async def ev_pay_ask(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  lang = lang_of(user)
  parts = callback.data.split(":")
  if len(parts) != 3 or not parts[2].isdigit():
    return
  event_id = int(parts[2])
  event = await session.get(Event, event_id)
  if not event or event.status == EventStatus.DELETED.value:
    await callback.answer(tx(user, "EVENT_NOT_FOUND"), show_alert=True)
    return
  if not event.price or event.price <= 0:
    await callback.answer(tx(user, "EVENT_FEE_NONE"), show_alert=True)
    return
  if await has_paid_event_fee(session, user.id, event.id):
    await callback.answer(tx(user, "EVENT_FEE_PAID"), show_alert=False)
    return
  if user.sparks_balance < event.price:
    await callback.answer(
      tx(user, "EVENT_NOT_ENOUGH", need=event.price, have=user.sparks_balance),
      show_alert=True,
    )
    return

  await safe_edit_text(
    callback.message,
    tx(user, "EVENT_FEE_CONFIRM", title=event.title, price=event.price, balance=user.sparks_balance),
    reply_markup=event_pay_confirm_kb(event.id, lang),
    redis=redis,
  )
  await callback.answer()


@router.callback_query(F.data == "ev:find")
async def ev_find(callback: CallbackQuery, session: AsyncSession, user: User, redis: Redis) -> None:
  lang = lang_of(user)
  result = await session.execute(select(EventCategory).where(EventCategory.is_active.is_(True)))
  cats = result.scalars().all()
  cats_data = [(str(c.id), category_label(c.name, lang, emoji=c.emoji or "")) for c in cats]
  await safe_edit_text(
    callback.message,
    t(user, "EVENTS_INTRO"),
    reply_markup=event_categories_kb(cats_data),
    redis=redis,
  )
  await callback.answer()


@router.callback_query(F.data.startswith("ev:cat:"))
async def ev_cat_browse(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  lang = lang_of(user)
  cat_id = int(callback.data.split(":")[-1])
  cat = await session.get(EventCategory, cat_id)
  event = await get_next_event(session, user, category_id=cat_id)
  if not event:
    empty_key = "EVENT_EMPTY_CAT"
    if cat:
      ft = (cat.filter_type or "type").strip().lower()
      name_l = (cat.name or "").lower()
      if ft == "time" or "сегодня" in name_l:
        empty_key = "EVENT_EMPTY_TODAY"
      elif ft == "geo" or "рядом" in name_l:
        empty_key = "EVENT_EMPTY_NEAR"
    await safe_edit_text(
      callback.message,
      tx(user, empty_key),
      reply_markup=events_menu_kb(lang),
      redis=redis,
    )
    await callback.answer()
    return
  org = await get_user_by_id(session, event.organizer_id)
  text = format_event_card(event, org, lang=lang)
  from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

  kb = InlineKeyboardMarkup(
    inline_keyboard=[
      [
        InlineKeyboardButton(text=lbl(lang, "ev_apply"), callback_data=f"ev:apply:{event.id}"),
        InlineKeyboardButton(text=lbl(lang, "ev_next"), callback_data=f"ev:next:{event.id}:{cat_id}"),
      ],
      [
        InlineKeyboardButton(text=lbl(lang, "ev_share"), callback_data=f"ev:share:{event.id}"),
        InlineKeyboardButton(text=lbl(lang, "ev_report"), callback_data=f"ev:report:{event.id}"),
      ],
    ]
  )
  await safe_edit_media(callback.message, text, event.photo_file_id, reply_markup=kb, redis=redis)
  await callback.answer()


@router.callback_query(F.data.startswith("ev:next:"))
async def ev_next(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  lang = lang_of(user)
  parts = callback.data.split(":")
  after_id = int(parts[2])
  cat_id = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None

  from bot.handlers.luma import try_show_next_luma_event

  if await try_show_next_luma_event(
    callback.message, user, session, redis, exclude=[after_id], edit=True
  ):
    await callback.answer()
    return

  event = await get_next_event(session, user, category_id=cat_id, after_id=after_id)
  if not event:
    await safe_edit_text(callback.message, tx(user, "EVENT_NO_MORE"), reply_markup=events_menu_kb(lang), redis=redis)
    await callback.answer()
    return
  org = await get_user_by_id(session, event.organizer_id)
  text = format_event_card(event, org, lang=lang)
  from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

  cat_part = f":{cat_id}" if cat_id else ""
  kb = InlineKeyboardMarkup(
    inline_keyboard=[
      [
        InlineKeyboardButton(text=lbl(lang, "ev_apply"), callback_data=f"ev:apply:{event.id}"),
        InlineKeyboardButton(text=lbl(lang, "ev_next"), callback_data=f"ev:next:{event.id}{cat_part}"),
      ],
      [
        InlineKeyboardButton(text=lbl(lang, "ev_share"), callback_data=f"ev:share:{event.id}"),
        InlineKeyboardButton(text=lbl(lang, "ev_report"), callback_data=f"ev:report:{event.id}"),
      ],
    ]
  )
  await safe_edit_media(callback.message, text, event.photo_file_id, reply_markup=kb, redis=redis)
  await callback.answer()


@router.callback_query(F.data.startswith("ev:apply:"))
async def ev_apply(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
  lang = lang_of(user)
  event_id = int(callback.data.split(":")[-1])
  existing = await session.execute(
    select(EventApplication).where(
      EventApplication.event_id == event_id,
      EventApplication.user_id == user.id,
    )
  )
  app_row = existing.scalar_one_or_none()
  if app_row:
    if app_row.status == ApplicationStatus.ACCEPTED.value:
      await callback.answer(tx(user, "EVENT_APP_ACCEPTED_STATUS"), show_alert=False)
    elif app_row.status == ApplicationStatus.PENDING.value:
      await callback.answer(tx(user, "EVENT_APP_PENDING"), show_alert=False)
    else:
      await callback.answer(tx(user, "EVENT_APP_REJECTED_STATUS"), show_alert=False)
    return

  app = EventApplication(event_id=event_id, user_id=user.id)
  session.add(app)
  await session.flush()

  event = await session.get(Event, event_id)
  if event:
    org = await get_user_by_id(session, event.organizer_id)
    applicant = await get_user_by_id(session, user.id) or user
    if org:
      try:
        await _send_application_card(
          callback.bot,
          org.telegram_id,
          applicant,
          app.id,
          prefix=tx(org, "EVENT_NEW_APP", title=event.title),
          lang=lang_of(org),
        )
      except Exception:
        pass

  await callback.answer(tx(user, "EVENT_APP_SENT"), show_alert=False)


@router.callback_query(F.data.startswith("ev:share:"))
@router.callback_query(F.data.startswith("ev:inv:link:"))
async def ev_share(callback: CallbackQuery, user: User, redis: Redis) -> None:
  event_id = callback.data.split(":")[-1]
  link = f"https://t.me/{settings.bot_username}?start=event_{event_id}"
  await safe_edit_text(
    callback.message,
    tx(user, "EVENT_SHARE", link=link),
    redis=redis,
  )
  await callback.answer()


@router.callback_query(F.data.startswith("ev:report:"))
async def ev_report_start(callback: CallbackQuery, user: User, redis: Redis) -> None:
  event_id = int(callback.data.split(":")[-1])
  await safe_edit_text(
    callback.message,
    t(user, "EVENT_REPORT_ASK"),
    reply_markup=complaint_reasons_kb(event_id, kind="event", lang=lang_of(user)),
    redis=redis,
  )
  await callback.answer()


@router.callback_query(F.data.startswith("ev:reason:"))
async def ev_report_reason(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  lang = lang_of(user)
  parts = callback.data.split(":")
  reason_code, event_id = parts[2], int(parts[3])
  label = complaint_reason_label(lang, reason_code)
  event = await session.get(Event, event_id)
  session.add(
    Complaint(
      reporter_id=user.id,
      target_user_id=event.organizer_id if event else None,
      event_id=event_id,
      complaint_type="event",
      text=f"{reason_code}: {label}",
    )
  )
  await safe_edit_text(callback.message, t(user, "RATE_REPORT_DONE"), reply_markup=events_menu_kb(lang), redis=redis)
  await callback.answer()


@router.callback_query(F.data.startswith("ev:mg:apps:"))
async def ev_apps(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  lang = lang_of(user)
  event_id = int(callback.data.split(":")[-1])
  result = await session.execute(
    select(EventApplication).where(
      EventApplication.event_id == event_id,
      EventApplication.status == "pending",
    )
  )
  apps = list(result.scalars().all())
  if not apps:
    await safe_edit_text(callback.message, tx(user, "EVENT_NO_APPS"), redis=redis)
    await callback.answer()
    return

  first = True
  for app in apps:
    u = await get_user_by_id(session, app.user_id)
    if not u:
      continue
    text = format_other_profile(u, lang)
    kb = app_decision_kb(app.id, lang=lang)
    if first:
      await safe_edit_media(callback.message, text, u.photo_file_id, reply_markup=kb, redis=redis)
      first = False
    else:
      if u.photo_file_id:
        await callback.message.answer_photo(u.photo_file_id, caption=text, reply_markup=kb)
      else:
        await callback.message.answer(text, reply_markup=kb)
  await callback.answer()


@router.callback_query(F.data.startswith("ev:app:ok:"))
async def ev_app_ok(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
  app_id = int(callback.data.split(":")[-1])
  app = await session.get(EventApplication, app_id)
  if not app or app.status != "pending":
    await callback.answer(tx(user, "EVENT_APP_ALREADY"), show_alert=False)
    return

  app.status = "accepted"
  event = await session.get(Event, app.event_id)
  applicant = await get_user_by_id(session, app.user_id)
  if event and applicant:
    if applicant.gender == "male":
      event.men_count += 1
    else:
      event.women_count += 1
    applicant.events_attended += 1
    try:
      await callback.bot.send_message(
        applicant.telegram_id,
        f"✅ {tx(applicant, 'EVENT_APP_ACCEPTED_STATUS')} — «{event.title}»",
      )
    except Exception:
      pass

  try:
    await callback.message.edit_reply_markup(reply_markup=None)
  except Exception:
    pass
  await callback.answer(lbl(lang_of(user), "app_accept"))


@router.callback_query(F.data.startswith("ev:app:no:"))
async def ev_app_no(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
  app_id = int(callback.data.split(":")[-1])
  app = await session.get(EventApplication, app_id)
  if not app or app.status != "pending":
    await callback.answer(tx(user, "EVENT_APP_ALREADY"), show_alert=False)
    return

  app.status = "rejected"
  event = await session.get(Event, app.event_id)
  applicant = await get_user_by_id(session, app.user_id)
  if event and applicant:
    try:
      await callback.bot.send_message(
        applicant.telegram_id,
        f"{tx(applicant, 'EVENT_APP_REJECTED_STATUS')} — «{event.title}»",
      )
    except Exception:
      pass

  try:
    await callback.message.edit_reply_markup(reply_markup=None)
  except Exception:
    pass
  await callback.answer(lbl(lang_of(user), "app_reject"))


@router.callback_query(F.data.startswith("ev:mg:invite:"))
async def ev_invite(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  lang = lang_of(user)
  event_id = int(callback.data.split(":")[-1])
  event = await session.get(Event, event_id)
  mass_ok = is_premium(user) and event and event.mass_invites_used < 5
  await safe_edit_text(
    callback.message,
    tx(user, "EVENT_INVITE_PEOPLE"),
    reply_markup=invite_kb(event_id, mass_ok, lang),
    redis=redis,
  )
  await callback.answer()


@router.callback_query(F.data.startswith("ev:mg:close:"))
async def ev_close_ask(callback: CallbackQuery, user: User, redis: Redis) -> None:
  lang = lang_of(user)
  event_id = int(callback.data.split(":")[-1])
  await safe_edit_text(
    callback.message,
    t(user, "EVENT_CLOSE_CONFIRM"),
    reply_markup=event_close_confirm_kb(event_id, lang),
    redis=redis,
  )
  await callback.answer()


@router.callback_query(F.data.startswith("ev:mg:closeok:"))
async def ev_close_ok(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  event_id = int(callback.data.split(":")[-1])
  event = await session.get(Event, event_id)
  if not event or event.organizer_id != user.id:
    await callback.answer(t(user, "EVENT_NOT_FOUND"), show_alert=True)
    return
  link = await close_event_and_invite(session, callback.bot, event)
  await sync_events_organized(session, user)
  await safe_edit_text(callback.message, t(user, "EVENT_CLOSE_DONE", link=link), redis=redis)
  await callback.answer()


@router.callback_query(F.data.startswith("ev:mg:delask:"))
async def ev_delete_ask(callback: CallbackQuery, user: User, redis: Redis) -> None:
  lang = lang_of(user)
  event_id = int(callback.data.split(":")[-1])
  await safe_edit_text(
    callback.message,
    t(user, "EVENT_DELETE_CONFIRM"),
    reply_markup=event_delete_confirm_kb(event_id, lang),
    redis=redis,
  )
  await callback.answer()


@router.callback_query(F.data.startswith("ev:mg:del:"))
async def ev_delete(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  event_id = int(callback.data.split(":")[-1])
  event = await session.get(Event, event_id)
  if event and event.organizer_id == user.id:
    event.status = EventStatus.DELETED.value
    await sync_events_organized(session, user)
    await safe_edit_text(callback.message, t(user, "EVENT_DELETED"), redis=redis)
  await callback.answer()


@router.callback_query(F.data.startswith("ev:boost:"))
async def ev_boost(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  event_id = int(callback.data.split(":")[-1])
  event = await session.get(Event, event_id)
  if not event:
    await callback.answer(t(user, "EVENT_NOT_FOUND"), show_alert=True)
    return
  try:
    price = await boost_event(session, user, event)
    if price > 0:
      await pay_blogger_commission(session, user, price, purpose="event_boost")
    key = "EVENT_BOOST_FREE_OK" if price <= 0 else "EVENT_BOOST_OK"
    await callback.answer(t(user, key, price=price), show_alert=True)
  except ValueError as e:
    await callback.answer(service_err(user, e), show_alert=True)


@router.callback_query(F.data.startswith("ev:pin:"))
async def ev_pin(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  event_id = int(callback.data.split(":")[-1])
  event = await session.get(Event, event_id)
  if not event:
    await callback.answer(t(user, "EVENT_NOT_FOUND"), show_alert=True)
    return
  try:
    price = await pin_event(session, user, event, hours=1)
    await pay_blogger_commission(session, user, price, purpose="event_pin")
    await callback.answer(t(user, "EVENT_PIN_OK", hours=1, price=price), show_alert=True)
  except ValueError as e:
    await callback.answer(service_err(user, e), show_alert=True)


@router.callback_query(F.data.startswith("ev:inv:mass:"))
async def ev_mass_invite(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  event_id = int(callback.data.split(":")[-1])
  event = await session.get(Event, event_id)
  if not event:
    await callback.answer(t(user, "EVENT_NOT_FOUND"), show_alert=True)
    return
  try:
    sent = await send_mass_invites(session, callback.bot, user, event)
    await safe_edit_text(callback.message, t(user, "EVENT_MASS_SENT", count=sent), redis=redis)
  except ValueError as e:
    await callback.answer(service_err(user, e), show_alert=True)
    return
  await callback.answer()


@router.callback_query(F.data.startswith("ev:mg:parts:"))
async def ev_participants(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  lang = lang_of(user)
  event_id = int(callback.data.split(":")[-1])
  event = await session.get(Event, event_id)
  if not event:
    await callback.answer(tx(user, "EVENT_NOT_FOUND"), show_alert=True)
    return

  result = await session.execute(
    select(EventApplication).where(
      EventApplication.event_id == event_id,
      EventApplication.status == ApplicationStatus.ACCEPTED.value,
    )
  )
  apps = list(result.scalars().all())
  if not apps:
    await safe_edit_text(
      callback.message,
      tx(user, "EVENT_PARTS_EMPTY", title=event.title),
      reply_markup=await _event_manage_kb(session, user, event.id, False, lang),
      redis=redis,
    )
    await callback.answer()
    return

  links: list[tuple[str, str]] = []
  for app in apps:
    u = await get_user_by_id(session, app.user_id)
    if not u:
      continue
    gender = {
      "male": tx(user, "EVENT_GENDER_M"),
      "female": tx(user, "EVENT_GENDER_F"),
    }.get(u.gender or "", "?")
    label = f"{u.display_name}, {u.age or '—'} ({gender})"
    if u.username:
      url = f"https://t.me/{u.username}"
    else:
      url = f"tg://user?id={u.telegram_id}"
    links.append((label, url))

  await safe_edit_text(
    callback.message,
    tx(user, "EVENT_PARTS_LIST", title=event.title, count=len(links)),
    reply_markup=event_participants_kb(event.id, links, lang),
    redis=redis,
  )
  await callback.answer()


@router.callback_query(F.data.startswith("ev:mg:back:"))
async def ev_manage_back(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  lang = lang_of(user)
  event_id = int(callback.data.split(":")[-1])
  event = await session.get(Event, event_id)
  if not event:
    await callback.answer(tx(user, "EVENT_NOT_FOUND"), show_alert=True)
    return
  mass_ok = is_premium(user) and event.mass_invites_used < 5
  mark = "🟢" if event.status == EventStatus.ACTIVE.value else "🔒"
  await safe_edit_text(
    callback.message,
    tx(
      user,
      "EVENT_MANAGE_HEADER",
      mark=mark,
      title=event.title,
      city=event.city,
      date=event.event_date,
      time=event.event_time,
    ),
    reply_markup=await _event_manage_kb(session, user, event.id, mass_ok, lang),
    redis=redis,
  )
  await callback.answer()


@router.callback_query(F.data.startswith("ev:mg:edit:"))
async def ev_edit_menu(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  lang = lang_of(user)
  event_id = int(callback.data.split(":")[-1])
  event = await session.get(Event, event_id)
  if not event:
    await callback.answer(tx(user, "EVENT_NOT_FOUND"), show_alert=True)
    return
  await safe_edit_text(
    callback.message,
    tx(user, "EVENT_EDIT_WHAT", title=event.title),
    reply_markup=event_edit_fields_kb(event.id, lang),
    redis=redis,
  )
  await callback.answer()


_EDIT_FIELDS = {
  "title": ("EDIT_ASK_TITLE", "title"),
  "city": ("EDIT_ASK_CITY", "city"),
  "address": ("EDIT_ASK_ADDRESS", "address"),
  "datetime": ("EDIT_ASK_DATETIME", "datetime"),
  "price": ("EDIT_ASK_PRICE", "price"),
  "description": ("EDIT_ASK_DESC", "description"),
  "photo": ("EDIT_ASK_PHOTO", "photo"),
}


@router.callback_query(F.data.startswith("ev:ed:"))
async def ev_edit_field_start(callback: CallbackQuery, state: FSMContext, user: User, redis: Redis) -> None:
  parts = callback.data.split(":")
  if len(parts) < 4:
    await callback.answer()
    return
  field, event_id = parts[2], int(parts[3])
  prompt_info = _EDIT_FIELDS.get(field)
  if not prompt_info:
    await callback.answer(tx(user, "EDIT_FIELD_UNKNOWN"), show_alert=True)
    return
  tx_key, field_key = prompt_info
  await state.set_state(EventEdit.waiting)
  prompt = await safe_edit_text(callback.message, tx(user, tx_key), redis=redis)
  await state.update_data(
    event_id=event_id,
    edit_field=field_key,
    prompt_message_id=prompt.message_id if prompt else callback.message.message_id,
  )
  await callback.answer()


@router.message(EventEdit.waiting, F.photo)
async def ev_edit_photo_save(
  message: Message, state: FSMContext, user: User, session: AsyncSession, redis: Redis
) -> None:
  lang = lang_of(user)
  data = await state.get_data()
  if data.get("edit_field") != "photo":
    await message.answer(tx(user, "EVENT_NEED_TEXT"))
    return
  event = await session.get(Event, data["event_id"])
  if not event or event.organizer_id != user.id:
    await state.clear()
    await cleanup_user_and_prompt(message, prompt_message_id=data.get("prompt_message_id"))
    await send_ui(message, tx(user, "EVENT_NOT_FOUND"), reply_markup=events_menu_kb(lang), redis=redis)
    return
  event.photo_file_id = message.photo[-1].file_id
  await state.clear()
  await cleanup_user_and_prompt(message, prompt_message_id=data.get("prompt_message_id"))
  mass_ok = is_premium(user) and event.mass_invites_used < 5
  await send_ui(
    message,
    f"{tx(user, 'EVENT_PHOTO_UPDATED')}\n\n"
    + tx(
      user,
      "EVENT_MANAGE_HEADER",
      mark="🟢",
      title=event.title,
      city=event.city,
      date=event.event_date,
      time=event.event_time,
    ),
    reply_markup=await _event_manage_kb(session, user, event.id, mass_ok, lang),
    redis=redis,
  )


@router.message(EventEdit.waiting, F.text)
async def ev_edit_text_save(
  message: Message, state: FSMContext, user: User, session: AsyncSession, redis: Redis
) -> None:
  lang = lang_of(user)
  data = await state.get_data()
  field = data.get("edit_field")
  if field == "photo":
    await message.answer(tx(user, "EVENT_NEED_PHOTO"))
    return
  event = await session.get(Event, data["event_id"])
  if not event or event.organizer_id != user.id:
    await state.clear()
    await cleanup_user_and_prompt(message, prompt_message_id=data.get("prompt_message_id"))
    await send_ui(message, tx(user, "EVENT_NOT_FOUND"), reply_markup=events_menu_kb(lang), redis=redis)
    return

  value = message.text.strip()
  if field == "title":
    event.title = value[:255]
  elif field == "city":
    event.city = value[:255]
  elif field == "address":
    event.address = value[:512]
  elif field == "datetime":
    parts = value.split(maxsplit=1)
    event.event_date = parts[0]
    event.event_time = parts[1] if len(parts) > 1 else event.event_time
  elif field == "price":
    event.price = int(value) if value.isdigit() else event.price
  elif field == "description":
    event.description = value[:2000]
  else:
    await message.answer(tx(user, "EDIT_FIELD_UNKNOWN"))
    return

  await state.clear()
  await cleanup_user_and_prompt(message, prompt_message_id=data.get("prompt_message_id"))
  mass_ok = is_premium(user) and event.mass_invites_used < 5
  await send_ui(
    message,
    f"{tx(user, 'EVENT_SAVED')}\n\n"
    + tx(
      user,
      "EVENT_MANAGE_HEADER",
      mark="🟢",
      title=event.title,
      city=event.city,
      date=event.event_date,
      time=event.event_time,
    ),
    reply_markup=await _event_manage_kb(session, user, event.id, mass_ok, lang),
    redis=redis,
  )
