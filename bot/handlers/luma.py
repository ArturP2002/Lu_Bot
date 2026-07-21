"""AI-помощник LUMA."""

from __future__ import annotations

import json

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.keyboards import event_card_kb, luma_kb, rate_card_kb
from bot.states.states import LumaChat
from bot.texts.formatters import format_other_profile
from bot.texts.i18n import lang_of, t
from bot.texts.ui_labels import service_err, tx
from bot.utils.messaging import cleanup_user_and_prompt, edit_or_send, safe_edit_text, send_ui
from models import Event, EventStatus, User
from services.luma_ai_service import ask_luma, search_events, search_people
from services.user_service import get_user_by_id, is_premium

router = Router()

_LUMA_TTL = 3600
_PEOPLE_QUEUE = "luma:people_queue:{user_id}"
_PEOPLE_BROWSE = "luma:people_browse:{user_id}"
_EVENTS_QUEUE = "luma:events_queue:{user_id}"
_EVENTS_BROWSE = "luma:events_browse:{user_id}"


async def _clear_keys(redis: Redis | None, *keys: str) -> None:
  if redis and keys:
    await redis.delete(*keys)


async def clear_luma_people_browse(redis: Redis | None, user_id: int) -> None:
  await _clear_keys(redis, _PEOPLE_QUEUE.format(user_id=user_id), _PEOPLE_BROWSE.format(user_id=user_id))


async def clear_luma_events_browse(redis: Redis | None, user_id: int) -> None:
  await _clear_keys(redis, _EVENTS_QUEUE.format(user_id=user_id), _EVENTS_BROWSE.format(user_id=user_id))


async def clear_luma_browse(redis: Redis | None, user_id: int) -> None:
  await clear_luma_people_browse(redis, user_id)
  await clear_luma_events_browse(redis, user_id)


async def _save_queue(redis: Redis, browse_key: str, queue_key: str, remaining_ids: list[int]) -> None:
  await redis.set(browse_key, "1", ex=_LUMA_TTL)
  await redis.set(queue_key, json.dumps(remaining_ids), ex=_LUMA_TTL)


async def _pop_queue_id(
  redis: Redis,
  *,
  browse_key: str,
  queue_key: str,
  exclude: list[int] | None = None,
) -> int | None:
  raw = await redis.get(queue_key)
  if raw is None:
    await redis.delete(browse_key, queue_key)
    return None
  try:
    ids = json.loads(raw)
  except (TypeError, json.JSONDecodeError):
    await redis.delete(browse_key, queue_key)
    return None
  if not isinstance(ids, list):
    await redis.delete(browse_key, queue_key)
    return None
  skip = set(exclude or [])
  ids = [int(i) for i in ids if int(i) not in skip]
  if not ids:
    await redis.delete(browse_key, queue_key)
    return None
  next_id = ids[0]
  await redis.set(queue_key, json.dumps(ids[1:]), ex=_LUMA_TTL)
  return next_id


async def is_luma_people_browse(redis: Redis | None, user_id: int) -> bool:
  return bool(redis and await redis.get(_PEOPLE_BROWSE.format(user_id=user_id)))


async def is_luma_events_browse(redis: Redis | None, user_id: int) -> bool:
  return bool(redis and await redis.get(_EVENTS_BROWSE.format(user_id=user_id)))


async def show_luma_person_card(
  message: Message,
  viewer: User,
  profile: User,
  *,
  redis: Redis | None = None,
  edit: bool = False,
  finalize_previous: bool = False,
) -> None:
  text = format_other_profile(profile, lang_of(viewer))
  kb = rate_card_kb(profile.id, lang_of(viewer))
  await edit_or_send(
    message,
    text,
    photo_file_id=profile.photo_file_id,
    reply_markup=kb,
    redis=redis,
    edit=edit,
    track=False,
    finalize_previous=finalize_previous,
  )


async def show_luma_event_card(
  message: Message,
  viewer: User,
  event: Event,
  session: AsyncSession,
  *,
  redis: Redis | None = None,
  edit: bool = False,
) -> None:
  from bot.handlers.events import format_event_card

  lang = lang_of(viewer)
  org = await get_user_by_id(session, event.organizer_id)
  text = format_event_card(event, org, lang=lang)
  await edit_or_send(
    message,
    text,
    photo_file_id=event.photo_file_id,
    reply_markup=event_card_kb(event.id, lang),
    redis=redis,
    edit=edit,
  )


async def present_luma_people(
  message: Message,
  viewer: User,
  session: AsyncSession,
  people: list[User],
  *,
  redis: Redis,
  edit: bool = False,
) -> None:
  await clear_luma_events_browse(redis, viewer.id)
  if not people:
    await clear_luma_people_browse(redis, viewer.id)
    await edit_or_send(
      message,
      tx(viewer, "LUMA_PEOPLE_EMPTY"),
      reply_markup=luma_kb(is_premium(viewer), lang_of(viewer)),
      redis=redis,
      edit=edit,
    )
    return

  first_id = people[0].id
  remaining = [p.id for p in people[1:]]
  await _save_queue(
    redis,
    _PEOPLE_BROWSE.format(user_id=viewer.id),
    _PEOPLE_QUEUE.format(user_id=viewer.id),
    remaining,
  )
  profile = await get_user_by_id(session, first_id)
  if not profile:
    await clear_luma_people_browse(redis, viewer.id)
    await edit_or_send(
      message,
      tx(viewer, "LUMA_PEOPLE_EMPTY"),
      reply_markup=luma_kb(is_premium(viewer), lang_of(viewer)),
      redis=redis,
      edit=edit,
    )
    return
  await show_luma_person_card(message, viewer, profile, redis=redis, edit=edit)


async def present_luma_events(
  message: Message,
  viewer: User,
  session: AsyncSession,
  events: list[Event],
  *,
  redis: Redis,
  edit: bool = False,
) -> None:
  await clear_luma_people_browse(redis, viewer.id)
  if not events:
    await clear_luma_events_browse(redis, viewer.id)
    await edit_or_send(
      message,
      tx(viewer, "LUMA_EVENTS_EMPTY"),
      reply_markup=luma_kb(is_premium(viewer), lang_of(viewer)),
      redis=redis,
      edit=edit,
    )
    return

  first_id = events[0].id
  remaining = [e.id for e in events[1:]]
  await _save_queue(
    redis,
    _EVENTS_BROWSE.format(user_id=viewer.id),
    _EVENTS_QUEUE.format(user_id=viewer.id),
    remaining,
  )
  event = await session.get(Event, first_id)
  if not event or event.status != EventStatus.ACTIVE.value:
    await clear_luma_events_browse(redis, viewer.id)
    await edit_or_send(
      message,
      tx(viewer, "LUMA_EVENTS_EMPTY"),
      reply_markup=luma_kb(is_premium(viewer), lang_of(viewer)),
      redis=redis,
      edit=edit,
    )
    return
  await show_luma_event_card(message, viewer, event, session, redis=redis, edit=edit)


async def try_show_next_luma_person(
  message: Message,
  viewer: User,
  session: AsyncSession,
  redis: Redis | None,
  exclude: list[int] | None = None,
  *,
  edit: bool = True,
  finalize_previous: bool = False,
) -> bool:
  """Если активен просмотр выдачи LUMA — показать следующую анкету. True = обработано."""
  if not redis or not await is_luma_people_browse(redis, viewer.id):
    return False

  while True:
    next_id = await _pop_queue_id(
      redis,
      browse_key=_PEOPLE_BROWSE.format(user_id=viewer.id),
      queue_key=_PEOPLE_QUEUE.format(user_id=viewer.id),
      exclude=exclude,
    )
    if next_id is None:
      await edit_or_send(
        message,
        tx(viewer, "LUMA_PEOPLE_DONE"),
        reply_markup=luma_kb(is_premium(viewer), lang_of(viewer)),
        redis=redis,
        edit=edit,
        finalize_previous=finalize_previous,
      )
      return True

    profile = await get_user_by_id(session, next_id)
    if not profile or profile.disabled or profile.is_banned:
      continue

    await show_luma_person_card(
      message, viewer, profile, redis=redis, edit=edit, finalize_previous=finalize_previous
    )
    return True


async def try_show_next_luma_event(
  message: Message,
  viewer: User,
  session: AsyncSession,
  redis: Redis | None,
  exclude: list[int] | None = None,
  *,
  edit: bool = True,
) -> bool:
  """Если активен просмотр тусовок LUMA — показать следующую. True = обработано."""
  if not redis or not await is_luma_events_browse(redis, viewer.id):
    return False

  while True:
    next_id = await _pop_queue_id(
      redis,
      browse_key=_EVENTS_BROWSE.format(user_id=viewer.id),
      queue_key=_EVENTS_QUEUE.format(user_id=viewer.id),
      exclude=exclude,
    )
    if next_id is None:
      await edit_or_send(
        message,
        tx(viewer, "LUMA_EVENTS_DONE"),
        reply_markup=luma_kb(is_premium(viewer), lang_of(viewer)),
        redis=redis,
        edit=edit,
      )
      return True

    event = await session.get(Event, next_id)
    if not event or event.status != EventStatus.ACTIVE.value:
      continue

    await show_luma_event_card(message, viewer, event, session, redis=redis, edit=edit)
    return True


async def show_luma(
  message: Message,
  user: User,
  *,
  redis: Redis | None = None,
  edit: bool = False,
) -> None:
  await clear_luma_browse(redis, user.id)
  await edit_or_send(
    message,
    t(user, "LUMA_INTRO"),
    reply_markup=luma_kb(is_premium(user), lang_of(user)),
    redis=redis,
    edit=edit,
  )


@router.callback_query(F.data == "luma:ask")
@router.callback_query(F.data == "luma:people")
@router.callback_query(F.data == "luma:events")
async def luma_ask_start(callback: CallbackQuery, state: FSMContext, user: User, redis: Redis) -> None:
  mode = callback.data.split(":")[-1]
  await clear_luma_browse(redis, user.id)
  await state.set_state(LumaChat.waiting)
  await state.update_data(luma_mode=mode)
  prompt = await safe_edit_text(callback.message, t(user, "LUMA_ASK"), redis=redis)
  await state.update_data(prompt_message_id=prompt.message_id if prompt else callback.message.message_id)
  await callback.answer()


@router.message(LumaChat.waiting, F.text)
async def luma_ask(
  message: Message, state: FSMContext, user: User, session: AsyncSession, redis: Redis
) -> None:
  data = await state.get_data()
  prompt_id = data.get("prompt_message_id")
  mode = data.get("luma_mode", "ask")
  await state.clear()
  await cleanup_user_and_prompt(message, prompt_message_id=prompt_id)
  try:
    if mode == "people":
      people = await search_people(session, user, message.text, limit=10, use_ai_parse=True)
      await present_luma_people(message, user, session, people, redis=redis, edit=False)
      return
    if mode == "events":
      events = await search_events(session, user, message.text, limit=10, use_ai_parse=True)
      await present_luma_events(message, user, session, events, redis=redis, edit=False)
      return

    answer = await ask_luma(session, redis, user, message.text)
    await send_ui(message, answer, reply_markup=luma_kb(is_premium(user), lang_of(user)), redis=redis)
  except ValueError as e:
    if str(e) == "AI_LIMIT":
      await send_ui(message, t(user, "LUMA_LIMIT"), reply_markup=luma_kb(is_premium(user), lang_of(user)), redis=redis)
    else:
      await send_ui(message, service_err(user, e), reply_markup=luma_kb(is_premium(user), lang_of(user)), redis=redis)
