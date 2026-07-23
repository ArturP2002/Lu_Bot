"""Обработчики профиля."""

import random
import string
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.keyboards import (
    disable_confirm_kb,
    disable_goodbye_kb,
    gender_kb,
    language_inline_kb,
    payment_link_kb,
    payment_method_kb,
    premium_kb,
    profile_kb,
    rating_reset_kb,
    referral_kb,
    referral_standard_kb,
    seeking_kb,
    sparks_action_kb,
    visible_kb,
)
from bot.states.states import ProfileEdit, SparksFlow, VerificationFlow
from bot.texts.formatters import format_own_profile
from bot.texts.i18n import GENDER_BUTTONS, SEEKING_BUTTONS, VISIBLE_BUTTONS, lang_of, normalize_lang, t
from bot.texts.ui_labels import service_err, tx
from bot.utils.messaging import (
    cleanup_user_and_prompt,
    edit_or_send,
    resolve_photo_file_id,
    safe_delete,
    safe_edit_text,
    send_ui,
)
from config import get_settings
from models import User, Verification
from models.entities import VerificationStatus
from services.blogger_service import apply_blogger, blogger_link, get_or_create_blogger
from services.referral_service import count_completed_referrals, get_available_rewards
from services.sparks_service import withdraw_sparks
from services.user_service import free_rating_reset_available, is_premium
from services.verification_service import verify_video_note

router = Router()
settings = get_settings()


async def show_profile(
  message: Message,
  user: User,
  *,
  session: AsyncSession | None = None,
  redis: Redis | None = None,
  edit: bool = False,
) -> None:
  if session is not None:
    from services.event_service import sync_events_organized

    await sync_events_organized(session, user)
  text = format_own_profile(user)
  kb = profile_kb(user.disabled, lang_of(user))
  photo_file_id = await resolve_photo_file_id(message.bot, user)
  await edit_or_send(
    message,
    text,
    photo_file_id=photo_file_id,
    reply_markup=kb,
    redis=redis,
    edit=edit,
  )


async def _start_prompt(
  callback: CallbackQuery,
  state: FSMContext,
  fsm_state,
  text: str,
  redis: Redis,
  *,
  reply_markup=None,
  extra: dict | None = None,
) -> None:
  await state.set_state(fsm_state)
  prompt = await safe_edit_text(callback.message, text, reply_markup=reply_markup, redis=redis)
  data = {"prompt_message_id": prompt.message_id if prompt else callback.message.message_id}
  if extra:
    data.update(extra)
  await state.update_data(**data)
  await callback.answer()


@router.callback_query(F.data == "prof:age")
async def prof_age_start(callback: CallbackQuery, state: FSMContext, user: User, redis: Redis) -> None:
  await _start_prompt(callback, state, ProfileEdit.age, t(user, "REG_ASK_AGE"), redis)


@router.message(ProfileEdit.age, F.text)
async def prof_age_save(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  data = await state.get_data()
  prompt_id = data.get("prompt_message_id")
  if not message.text.isdigit() or int(message.text) < 18:
    await message.answer(t(user, "ERR_AGE"))
    return
  user.age = int(message.text)
  await state.clear()
  await cleanup_user_and_prompt(message, prompt_message_id=prompt_id)
  await show_profile(message, user, redis=redis)


@router.callback_query(F.data == "prof:gender")
async def prof_gender_start(callback: CallbackQuery, state: FSMContext, user: User, redis: Redis) -> None:
  await state.set_state(ProfileEdit.gender)
  await safe_delete(callback.message)
  prompt = await send_ui(
    callback.message, t(user, "REG_ASK_GENDER"), reply_markup=gender_kb(lang_of(user)), redis=redis
  )
  await state.update_data(prompt_message_id=prompt.message_id if prompt else None)
  await callback.answer()


@router.message(ProfileEdit.gender, F.text)
async def prof_gender_save(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  mapping = GENDER_BUTTONS[normalize_lang(lang_of(user))]
  if message.text not in mapping:
    return
  data = await state.get_data()
  user.gender = mapping[message.text]
  await state.set_state(ProfileEdit.seeking)
  await cleanup_user_and_prompt(message, prompt_message_id=data.get("prompt_message_id"))
  prompt = await send_ui(message, t(user, "REG_ASK_SEEKING"), reply_markup=seeking_kb(lang_of(user)), redis=redis)
  await state.update_data(prompt_message_id=prompt.message_id)


@router.message(ProfileEdit.seeking, F.text)
async def prof_seeking_save(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  mapping = SEEKING_BUTTONS[normalize_lang(lang_of(user))]
  if message.text not in mapping:
    return
  data = await state.get_data()
  user.seeking = mapping[message.text]
  await state.set_state(ProfileEdit.visible_to)
  await cleanup_user_and_prompt(message, prompt_message_id=data.get("prompt_message_id"))
  prompt = await send_ui(message, t(user, "REG_ASK_VISIBLE"), reply_markup=visible_kb(lang_of(user)), redis=redis)
  await state.update_data(prompt_message_id=prompt.message_id)


@router.message(ProfileEdit.visible_to, F.text)
async def prof_visible_save(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  mapping = VISIBLE_BUTTONS[normalize_lang(lang_of(user))]
  if message.text not in mapping:
    return
  data = await state.get_data()
  prompt_id = data.get("prompt_message_id")
  user.visible_to = mapping[message.text]
  await state.clear()
  await cleanup_user_and_prompt(message, prompt_message_id=prompt_id)
  await show_profile(message, user, redis=redis)


@router.callback_query(F.data == "prof:lang")
async def prof_lang_start(callback: CallbackQuery, user: User, redis: Redis) -> None:
  await safe_edit_text(
    callback.message, t(user, "PROFILE_LANG"), reply_markup=language_inline_kb(), redis=redis
  )
  await callback.answer()


@router.callback_query(F.data.startswith("prof:lang:"))
async def prof_lang_save(callback: CallbackQuery, user: User, redis: Redis) -> None:
  lang = callback.data.split(":")[-1]
  user.language = normalize_lang(lang)
  await safe_edit_text(callback.message, t(user, "LANG_CHANGED"), reply_markup=profile_kb(user.disabled, lang_of(user)), redis=redis)
  await callback.answer()


@router.callback_query(F.data == "prof:photo")
async def prof_photo_start(callback: CallbackQuery, state: FSMContext, user: User, redis: Redis) -> None:
  await _start_prompt(callback, state, ProfileEdit.photo, tx(user, "PHOTO_ASK"), redis)


@router.message(ProfileEdit.photo, F.photo)
async def prof_photo_save(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  data = await state.get_data()
  prompt_id = data.get("prompt_message_id")
  user.photo_file_id = message.photo[-1].file_id
  await state.clear()
  await cleanup_user_and_prompt(message, prompt_message_id=prompt_id)
  await show_profile(message, user, redis=redis)


@router.callback_query(F.data == "prof:city")
async def prof_city_start(callback: CallbackQuery, state: FSMContext, user: User, redis: Redis) -> None:
  await _start_prompt(callback, state, ProfileEdit.city, tx(user, "CITY_ASK"), redis)


@router.message(ProfileEdit.city, F.text)
async def prof_city_save(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  data = await state.get_data()
  prompt_id = data.get("prompt_message_id")
  user.city = message.text.strip()[:255]
  await state.clear()
  await cleanup_user_and_prompt(message, prompt_message_id=prompt_id)
  await show_profile(message, user, redis=redis)


@router.callback_query(F.data == "prof:bio")
async def prof_bio_start(callback: CallbackQuery, state: FSMContext, user: User, redis: Redis) -> None:
  await _start_prompt(callback, state, ProfileEdit.bio, t(user, "REG_ASK_BIO"), redis)


@router.message(ProfileEdit.bio, F.text)
async def prof_bio_save(message: Message, state: FSMContext, user: User, redis: Redis) -> None:
  data = await state.get_data()
  prompt_id = data.get("prompt_message_id")
  user.bio = message.text.strip()[:1000]
  await state.clear()
  await cleanup_user_and_prompt(message, prompt_message_id=prompt_id)
  await show_profile(message, user, redis=redis)


@router.callback_query(F.data == "prof:premium")
async def prof_premium(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  lang = lang_of(user)
  if is_premium(user) and user.premium_until:
    from zoneinfo import ZoneInfo

    until = user.premium_until
    if until.tzinfo is None:
      until = until.replace(tzinfo=timezone.utc)
    until_local = until.astimezone(ZoneInfo("Europe/Moscow"))
    until_str = until_local.strftime("%d.%m.%Y %H:%M")
    await safe_edit_text(
      callback.message,
      t(user, "PREMIUM_ACTIVE", until=until_str),
      redis=redis,
      parse_mode="HTML",
    )
  else:
    from services.app_settings_service import get_setting_int

    premium_price = await get_setting_int(session, "premium_price")
    text = f"{t(user, 'PREMIUM_TITLE')}\n\n{t(user, 'PREMIUM_TEXT')}"
    await safe_edit_text(callback.message, text, reply_markup=premium_kb(premium_price, lang), redis=redis)
  await callback.answer()


@router.callback_query(F.data == "prof:premium:buy")
async def prof_premium_buy(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  from datetime import timedelta

  from services.app_settings_service import get_setting_int
  from services.blogger_service import pay_blogger_commission
  from services.sparks_service import add_transaction

  premium_price = await get_setting_int(session, "premium_price")
  if user.sparks_balance < premium_price:
    await callback.answer(t(user, "ERR_NOT_ENOUGH_SPARKS"), show_alert=True)
    return
  await add_transaction(session, user.id, -premium_price, "premium")
  await pay_blogger_commission(session, user, premium_price, purpose="premium")
  now = datetime.now(timezone.utc)
  base = user.premium_until if user.premium_until and user.premium_until > now else now
  if base.tzinfo is None:
    base = base.replace(tzinfo=timezone.utc)
  user.premium_until = base + timedelta(days=30)
  await safe_edit_text(callback.message, tx(user, "PREMIUM_ACTIVATED"), redis=redis)
  await callback.answer()


@router.callback_query(F.data == "prof:disable")
async def prof_disable(callback: CallbackQuery, user: User, redis: Redis) -> None:
  lang = lang_of(user)
  if user.disabled:
    user.disabled = False
    await show_profile(callback.message, user, redis=redis, edit=True)
  else:
    await safe_edit_text(
      callback.message,
      t(user, "PROFILE_DISABLE_CONFIRM"),
      reply_markup=disable_confirm_kb(lang),
      redis=redis,
    )
  await callback.answer()


@router.callback_query(F.data.in_({"prof:dis:no", "prof:dis:no2", "prof:dis:no3"}))
async def prof_disable_no(callback: CallbackQuery, user: User, redis: Redis) -> None:
  await safe_edit_text(callback.message, t(user, "PROFILE_DISABLED_CELEBRATE"), redis=redis)
  await callback.answer()


@router.callback_query(F.data == "prof:dis:yes")
async def prof_disable_yes(callback: CallbackQuery, user: User, redis: Redis) -> None:
  await safe_edit_text(
    callback.message,
    t(user, "PROFILE_DISABLE_GOODBYE"),
    reply_markup=disable_goodbye_kb(lang_of(user)),
    redis=redis,
  )
  await callback.answer()


@router.callback_query(F.data == "prof:dis:stay")
async def prof_disable_stay(callback: CallbackQuery, user: User, redis: Redis) -> None:
  await show_profile(callback.message, user, redis=redis, edit=True)
  await callback.answer()


@router.callback_query(F.data == "prof:dis:leave")
async def prof_disable_leave(callback: CallbackQuery, user: User, redis: Redis) -> None:
  user.disabled = True
  await safe_edit_text(callback.message, tx(user, "PROFILE_DISABLED_BYE"), redis=redis)
  await callback.answer()


@router.callback_query(F.data == "prof:referral")
async def prof_referral(callback: CallbackQuery, user: User, redis: Redis) -> None:
  await safe_edit_text(callback.message, t(user, "REFERRAL_INTRO"), reply_markup=referral_kb(lang_of(user)), redis=redis)
  await callback.answer()


@router.callback_query(F.data == "ref:standard")
async def ref_standard(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  lang = lang_of(user)
  count = await count_completed_referrals(session, user.id)
  text = (
    f"{t(user, 'REFERRAL_INTRO')}\n"
    f"{tx(user, 'REF_INVITED_LINE', count=count)}\n"
    f"https://t.me/{settings.bot_username}?start=ref_{user.referral_code}"
  )
  await safe_edit_text(callback.message, text, reply_markup=referral_standard_kb(lang), redis=redis)
  await callback.answer()


@router.callback_query(F.data == "ref:info")
async def ref_info(callback: CallbackQuery, user: User, redis: Redis) -> None:
  await safe_edit_text(callback.message, t(user, "REFERRAL_INFO"), redis=redis)
  await callback.answer()


@router.callback_query(F.data == "ref:claim")
async def ref_claim(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  rewards = await get_available_rewards(session, user)
  if not rewards:
    await callback.answer(tx(user, "REF_NO_REWARDS"), show_alert=True)
    return
  from services.referral_service import claim_referral_reward
  r = rewards[0]
  await claim_referral_reward(session, user, r["threshold"])
  await safe_edit_text(callback.message, tx(user, "REF_CLAIMED", reward=r["reward_type"]), redis=redis)
  await callback.answer()


@router.callback_query(F.data == "ref:blogger")
async def ref_blogger(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  profile = await apply_blogger(session, user)
  bp = await get_or_create_blogger(session, user)
  if profile.status == "pending":
    text = t(user, "BLOGGER_PENDING")
  else:
    text = t(
      user,
      "BLOGGER_INTRO",
      link=blogger_link(user),
      views=bp.views,
    )
  await safe_edit_text(callback.message, text, redis=redis)
  await callback.answer()


@router.callback_query(F.data == "prof:withdraw")
async def prof_withdraw(callback: CallbackQuery, state: FSMContext, user: User, redis: Redis) -> None:
  await state.set_state(SparksFlow.amount)
  prompt = await safe_edit_text(
    callback.message,
    f"{t(user, 'WITHDRAW_INFO')}\n\n{tx(user, 'WITHDRAW_AMOUNT')}",
    redis=redis,
  )
  await state.update_data(
    flow="withdraw",
    withdraw_method="stars",
    prompt_message_id=prompt.message_id if prompt else callback.message.message_id,
  )
  await callback.answer()


@router.callback_query(F.data.startswith("wd:method:"))
async def withdraw_method_chosen(callback: CallbackQuery, state: FSMContext, user: User, redis: Redis) -> None:
  await state.set_state(SparksFlow.amount)
  prompt = await safe_edit_text(callback.message, tx(user, "WITHDRAW_AMOUNT"), redis=redis)
  await state.update_data(
    flow="withdraw",
    withdraw_method="stars",
    prompt_message_id=prompt.message_id if prompt else callback.message.message_id,
  )
  await callback.answer()


@router.callback_query(F.data == "prof:sparks:amount")
async def prof_sparks_amount(callback: CallbackQuery, state: FSMContext, user: User, redis: Redis) -> None:
  await state.set_state(SparksFlow.amount)
  prompt = await safe_edit_text(callback.message, tx(user, "WITHDRAW_AMOUNT"), redis=redis)
  await state.update_data(
    flow="withdraw",
    withdraw_method="stars",
    prompt_message_id=prompt.message_id if prompt else callback.message.message_id,
  )
  await callback.answer()


@router.message(SparksFlow.amount, F.text)
async def sparks_amount(
  message: Message, state: FSMContext, user: User, session: AsyncSession, redis: Redis
) -> None:
  lang = lang_of(user)
  data = await state.get_data()
  prompt_id = data.get("prompt_message_id")
  if not message.text.isdigit():
    await message.answer(t(user, "ERR_INVALID_INPUT"))
    return
  amount = int(message.text)
  if amount <= 0:
    await message.answer(t(user, "ERR_INVALID_INPUT"))
    return

  if data.get("flow") == "withdraw":
    from services.app_settings_service import get_setting_int

    withdraw_min = await get_setting_int(session, "withdraw_min")
    if amount < withdraw_min:
      await message.answer(tx(user, "WITHDRAW_MIN", min=withdraw_min))
      return
    if user.sparks_balance < amount:
      await message.answer(t(user, "ERR_NOT_ENOUGH_SPARKS"))
      return

    method = "stars"
    await cleanup_user_and_prompt(message, prompt_message_id=prompt_id)
    await state.clear()
    await _create_withdraw_and_maybe_pay(
      message, user, session, redis, amount=amount, method=method, requisites=None
    )
    return

  await state.clear()
  await cleanup_user_and_prompt(message, prompt_message_id=prompt_id)
  await send_ui(
    message,
    t(user, "PAY_CHOOSE_METHOD", amount=amount),
    reply_markup=payment_method_kb(amount, lang),
    redis=redis,
    parse_mode="HTML",
  )


async def _create_withdraw_and_maybe_pay(
  message: Message,
  user: User,
  session: AsyncSession,
  redis: Redis,
  *,
  amount: int,
  method: str,
  requisites: str | None,
) -> None:
  try:
    amount, fee, net, req_id = await withdraw_sparks(
      session, user, amount, requisites, method=method
    )
  except ValueError as e:
    await send_ui(message, service_err(user, e), redis=redis)
    return

  status_line = ""
  if method == "stars":
    from models import WithdrawRequest
    from services.stars_payout_service import payout_stars_via_gifts

    req = await session.get(WithdrawRequest, req_id)
    result = await payout_stars_via_gifts(
      message.bot,
      user.telegram_id,
      net,
      note=f"LUMA: вывод #{req_id}",
    )
    if result.ok and req:
      req.status = "completed"
      req.payout_meta = f"gifts={result.gifts_sent};stars={result.stars_spent}"
      status_line = tx(user, "WITHDRAW_STARS_OK", gifts=result.gifts_sent, stars=result.stars_spent)
    elif req:
      req.status = "pending"
      req.payout_meta = result.error
      status_line = tx(user, "WITHDRAW_STARS_PENDING", error=result.error or "unknown")
    text = tx(
      user,
      "WITHDRAW_CREATED_STARS",
      id=req_id,
      amount=amount,
      net=net,
      fee=fee,
      status_line=status_line,
    )
  else:
    text = tx(user, "WITHDRAW_CREATED_REQ", id=req_id, amount=amount, net=net, fee=fee)

  await send_ui(message, text, redis=redis)


@router.message(SparksFlow.requisites, F.text)
async def sparks_requisites(
  message: Message, state: FSMContext, user: User, session: AsyncSession, redis: Redis
) -> None:
  data = await state.get_data()
  prompt_id = data.get("prompt_message_id")
  amount = int(data.get("amount") or 0)
  requisites = (message.text or "").strip()
  if len(requisites) < 5:
    await message.answer(t(user, "ERR_INVALID_INPUT"))
    return
  await state.clear()
  await cleanup_user_and_prompt(message, prompt_message_id=prompt_id)
  await _create_withdraw_and_maybe_pay(
    message, user, session, redis, amount=amount, method="requisites", requisites=requisites
  )


@router.callback_query(F.data == "prof:buy")
async def prof_buy(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, redis: Redis) -> None:
  from services.app_settings_service import get_setting_float

  await state.set_state(SparksFlow.amount)
  rub = await get_setting_float(session, "spark_price_rub")
  stars = await get_setting_float(session, "spark_price_stars")
  text = (
    f"{t(user, "BUY_SPARKS_INFO")}\n\n"
    f"{t(user, "BUY_SPARKS_RATES", rub=rub, stars=stars)}\n\n"
    f"{tx(user, 'BUY_SPARKS_ASK')}"
  )
  prompt = await safe_edit_text(callback.message, text, redis=redis)
  await state.update_data(
    flow="buy",
    prompt_message_id=prompt.message_id if prompt else callback.message.message_id,
  )
  await callback.answer()


@router.callback_query(F.data.startswith("pay:buy:yookassa:"))
async def pay_buy_yookassa(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  lang = lang_of(user)
  amount = int(callback.data.rsplit(":", 1)[-1])
  from services.yookassa_service import create_yookassa_payment

  try:
    link = await create_yookassa_payment(session, user, amount)
  except ValueError as e:
    await callback.answer(service_err(user, e) or t(user, "PAY_ERROR"), show_alert=True)
    return

  key = "PAY_YOOKASSA_STUB" if link.is_stub else "PAY_YOOKASSA_CREATED"
  text = t(user, key, amount=amount, rub=link.payment.amount_rub)
  await safe_edit_text(
    callback.message,
    text,
    reply_markup=payment_link_kb(link.confirmation_url, link.payment.id, is_stub=link.is_stub, lang=lang),
    redis=redis,
    parse_mode="HTML",
  )
  await callback.answer()


@router.callback_query(F.data.startswith("pay:buy:stars:"))
async def pay_buy_stars(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
  from services.app_settings_service import get_setting_float

  amount = int(callback.data.rsplit(":", 1)[-1])
  stars_per_spark = await get_setting_float(session, "spark_price_stars")
  stars_total = max(1, int(round(amount * stars_per_spark)))
  await callback.message.answer_invoice(
    title=tx(user, "BUY_SPARKS_TITLE"),
    description=tx(user, "BUY_SPARKS_DESC", amount=amount),
    payload=f"buy_sparks:{amount}",
    currency="XTR",
    prices=[LabeledPrice(label=tx(user, "BUY_SPARKS_LABEL"), amount=stars_total)],
  )
  await callback.answer()


@router.callback_query(F.data == "prof:reset_rating")
async def prof_reset_rating(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  from services.app_settings_service import get_setting_int

  reset_price = await get_setting_int(session, "rating_reset_price")
  free_ok = free_rating_reset_available(user)
  await safe_edit_text(
    callback.message,
    t(user, "RATING_RESET_INFO"),
    reply_markup=rating_reset_kb(
      is_premium(user),
      lang_of(user),
      free_available=free_ok,
      price=reset_price,
    ),
    redis=redis,
  )
  await callback.answer()


@router.callback_query(F.data == "prof:rating:pay")
async def prof_rating_pay(callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
  from services.app_settings_service import get_setting_int
  from services.sparks_service import add_transaction

  now = datetime.now(timezone.utc)
  if free_rating_reset_available(user):
    user.rating_avg = 0
    user.rating_count = 0
    user.free_rating_reset_at = now
    await safe_edit_text(callback.message, tx(user, "RATING_RESET_FREE"), redis=redis)
  else:
    reset_price = await get_setting_int(session, "rating_reset_price")
    if user.sparks_balance >= reset_price:
      await add_transaction(session, user.id, -reset_price, "rating_reset")
      user.rating_avg = 0
      user.rating_count = 0
      await safe_edit_text(callback.message, tx(user, "RATING_RESET_OK"), redis=redis)
    else:
      await callback.answer(t(user, "ERR_NOT_ENOUGH_SPARKS"), show_alert=True)
      return
  await callback.answer()


def _new_verify_challenge() -> tuple[str, str]:
  code = "".join(random.choices(string.digits, k=4))
  gesture = random.choice(["✌️", "👍", "🤟"])
  return code, gesture


@router.callback_query(F.data == "prof:verify")
async def prof_verify(callback: CallbackQuery, state: FSMContext, user: User, redis: Redis) -> None:
  if not user.photo_file_id:
    await safe_edit_text(callback.message, t(user, "VERIFY_NEED_PHOTO"), redis=redis)
    await callback.answer()
    return
  if user.verified:
    await callback.answer(tx(user, "VERIFY_ALREADY"), show_alert=True)
    return
  code, gesture = _new_verify_challenge()
  await state.set_state(VerificationFlow.video)
  prompt = await safe_edit_text(
    callback.message,
    t(user, "VERIFY_INFO", code=code, gesture=gesture),
    redis=redis,
    parse_mode="HTML",
  )
  await state.update_data(
    vcode=code,
    vgesture=gesture,
    prompt_message_id=prompt.message_id if prompt else callback.message.message_id,
  )
  await callback.answer()


@router.message(VerificationFlow.video, F.video | F.video_note)
async def prof_verify_video(
  message: Message, state: FSMContext, user: User, session: AsyncSession, redis: Redis
) -> None:
  data = await state.get_data()
  prompt_id = data.get("prompt_message_id")
  if not user.photo_file_id:
    await state.clear()
    await cleanup_user_and_prompt(message, prompt_message_id=prompt_id)
    await send_ui(message, t(user, "VERIFY_NEED_PHOTO"), redis=redis)
    return

  code = data.get("vcode")
  gesture = data.get("vgesture")
  if not code or not gesture:
    code, gesture = _new_verify_challenge()
    await state.update_data(vcode=code, vgesture=gesture)

  video_file_id = message.video.file_id if message.video else message.video_note.file_id
  await cleanup_user_and_prompt(message, prompt_message_id=prompt_id)
  status_msg = await send_ui(message, t(user, "VERIFY_CHECKING"), redis=redis)

  try:
    result = await verify_video_note(
      message.bot,
      photo_file_id=user.photo_file_id,
      video_file_id=video_file_id,
      expected_code=code,
      expected_gesture=gesture,
    )
  except Exception:
    await safe_edit_text(status_msg, t(user, "VERIFY_ERROR"), redis=redis)
    return

  v = Verification(
    user_id=user.id,
    code=code,
    gesture=gesture,
    video_file_id=video_file_id,
    status=VerificationStatus.APPROVED.value if result.passed else VerificationStatus.REJECTED.value,
  )
  session.add(v)

  if not result.passed:
    code, gesture = _new_verify_challenge()
    await state.update_data(
      vcode=code,
      vgesture=gesture,
      prompt_message_id=status_msg.message_id,
    )
    await safe_edit_text(
      status_msg,
      t(user, "VERIFY_FAILED", reason=result.reason, code=code, gesture=gesture),
      redis=redis,
      parse_mode="HTML",
    )
    return

  user.verified = True
  await state.clear()
  from services.referral_service import process_referral_on_verification
  await process_referral_on_verification(session, user)
  from bot.handlers.menu import send_menu
  await safe_edit_text(status_msg, t(user, "VERIFY_PASSED"), redis=redis)
  await send_menu(message, user, redis=redis)


@router.message(VerificationFlow.video)
async def prof_verify_video_invalid(message: Message, user: User) -> None:
  await message.answer(tx(user, "VERIFY_NEED_CIRCLE"))
