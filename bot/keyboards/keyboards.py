"""Клавиатуры бота."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
)

from bot.texts import messages as msg
from bot.texts.ui_labels import lbl, tx
from config import get_settings

# Главное меню (русские алиасы для обратной совместимости)
BTN_RATE = "Оценивать❤️"
BTN_EVENTS = "Тусовки🥳"
BTN_PROFILE = "Профиль👤"
BTN_GOALS = "Цели✨"
BTN_LUMA = "Лума🤵🏼‍♀️"
BTN_MENU = "Меню"

MAIN_MENU_BUTTONS = [BTN_RATE, BTN_EVENTS, BTN_PROFILE, BTN_GOALS, BTN_LUMA]


def main_menu_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    """Reply-клавиатура главного меню."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=lbl(lang, "rate", "menu")), KeyboardButton(text=lbl(lang, "events", "menu"))],
            [KeyboardButton(text=lbl(lang, "profile", "menu")), KeyboardButton(text=lbl(lang, "goals", "menu"))],
            [KeyboardButton(text=lbl(lang, "luma", "menu"))],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def limited_menu_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    """Меню до верификации."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=lbl(lang, "profile", "menu"))]],
        resize_keyboard=True,
        is_persistent=True,
    )


def admin_webapp_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    """Inline-кнопка открытия админ Mini App (только по /admin)."""
    url = get_settings().webapp_url.strip()
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=lbl(lang, "admin_open"), web_app=WebAppInfo(url=url))]
        ]
    )


def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


# Регистрация
def language_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Русский"), KeyboardButton(text="Беларуская")],
            [KeyboardButton(text="Українська"), KeyboardButton(text="Қазақша")],
        ],
        resize_keyboard=True,
    )


def gender_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    from bot.texts.i18n import GENDER_BUTTONS, normalize_lang

    labels = list(GENDER_BUTTONS[normalize_lang(lang)].keys())
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=labels[0]), KeyboardButton(text=labels[1])]],
        resize_keyboard=True,
    )


def seeking_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    from bot.texts.i18n import SEEKING_BUTTONS, normalize_lang

    labels = list(SEEKING_BUTTONS[normalize_lang(lang)].keys())
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=labels[0]), KeyboardButton(text=labels[1])]],
        resize_keyboard=True,
    )


def visible_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    from bot.texts.i18n import VISIBLE_BUTTONS, normalize_lang

    labels = list(VISIBLE_BUTTONS[normalize_lang(lang)].keys())
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=labels[0]), KeyboardButton(text=labels[1])],
            [KeyboardButton(text=labels[2])],
        ],
        resize_keyboard=True,
    )


def contact_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    from bot.texts.i18n import t

    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, "BTN_SEND_CONTACT"), request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def next_step_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    from bot.texts.i18n import t

    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t(lang, "BTN_NEXT_STEP"), callback_data="reg:next")]]
    )


# Профиль
def profile_kb(disabled: bool = False, lang: str = "ru") -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=lbl(lang, "prof_age"), callback_data="prof:age"),
            InlineKeyboardButton(text=lbl(lang, "prof_gender"), callback_data="prof:gender"),
        ],
        [
            InlineKeyboardButton(text=lbl(lang, "prof_photo"), callback_data="prof:photo"),
            InlineKeyboardButton(text=lbl(lang, "prof_city"), callback_data="prof:city"),
        ],
        [
            InlineKeyboardButton(text=lbl(lang, "prof_bio"), callback_data="prof:bio"),
            InlineKeyboardButton(text=lbl(lang, "prof_premium"), callback_data="prof:premium"),
        ],
        [
            InlineKeyboardButton(
                text=lbl(lang, "prof_enable" if disabled else "prof_disable"),
                callback_data="prof:disable",
            ),
            InlineKeyboardButton(text=lbl(lang, "prof_referral"), callback_data="prof:referral"),
        ],
        [
            InlineKeyboardButton(text=lbl(lang, "prof_lang"), callback_data="prof:lang"),
            InlineKeyboardButton(text=lbl(lang, "prof_verify"), callback_data="prof:verify"),
        ],
        [
            InlineKeyboardButton(text=lbl(lang, "prof_withdraw"), callback_data="prof:withdraw"),
            InlineKeyboardButton(text=lbl(lang, "prof_buy"), callback_data="prof:buy"),
        ],
        [InlineKeyboardButton(text=lbl(lang, "prof_reset"), callback_data="prof:reset_rating")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def language_inline_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Русский", callback_data="prof:lang:ru"),
                InlineKeyboardButton(text="Беларуская", callback_data="prof:lang:be"),
            ],
            [
                InlineKeyboardButton(text="Українська", callback_data="prof:lang:uk"),
                InlineKeyboardButton(text="Қазақша", callback_data="prof:lang:kk"),
            ],
        ]
    )


def disable_confirm_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=lbl(lang, "no"), callback_data="prof:dis:no"),
                InlineKeyboardButton(text=lbl(lang, "no_exact"), callback_data="prof:dis:no2"),
            ],
            [
                InlineKeyboardButton(text=lbl(lang, "no_rather"), callback_data="prof:dis:no3"),
                InlineKeyboardButton(text=lbl(lang, "yes"), callback_data="prof:dis:yes"),
            ],
        ]
    )


def disable_goodbye_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=lbl(lang, "stay"), callback_data="prof:dis:stay"),
                InlineKeyboardButton(text=lbl(lang, "goodbye"), callback_data="prof:dis:leave"),
            ]
        ]
    )


def premium_kb(price: int = 149, lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=tx(lang, "BUY_PREMIUM_BTN", price=price), callback_data="prof:premium:buy")]]
    )


def payment_method_kb(amount: int, lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=lbl(lang, "pay_yookassa"),
                    callback_data=f"pay:buy:yookassa:{amount}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=lbl(lang, "pay_stars"),
                    callback_data=f"pay:buy:stars:{amount}",
                )
            ],
        ]
    )


def payment_link_kb(url: str, payment_id: int, *, is_stub: bool, lang: str = "ru") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=lbl(lang, "pay_now"), url=url)]]
    if is_stub:
        rows.append(
            [InlineKeyboardButton(text=lbl(lang, "pay_stub"), callback_data=f"pay:stub:{payment_id}")]
        )
    else:
        rows.append(
            [InlineKeyboardButton(text=lbl(lang, "pay_check"), callback_data=f"pay:check:{payment_id}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def sparks_action_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=lbl(lang, "sparks_amount_btn"), callback_data="prof:sparks:amount")],
        ]
    )


def withdraw_method_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=lbl(lang, "wd_stars"), callback_data="wd:method:stars")],
            [InlineKeyboardButton(text=lbl(lang, "wd_requisites"), callback_data="wd:method:requisites")],
        ]
    )


def rating_reset_kb(is_premium: bool, lang: str = "ru") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=lbl(lang, "reset_rating_50"), callback_data="prof:rating:pay")]]
    if not is_premium:
        rows.append([InlineKeyboardButton(text=lbl(lang, "buy_premium"), callback_data="prof:premium")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def referral_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=lbl(lang, "ref_standard"), callback_data="ref:standard"),
                InlineKeyboardButton(text=lbl(lang, "ref_blogger"), callback_data="ref:blogger"),
            ]
        ]
    )


def referral_standard_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=lbl(lang, "ref_info"), callback_data="ref:info"),
                InlineKeyboardButton(text=lbl(lang, "ref_claim"), callback_data="ref:claim"),
            ]
        ]
    )


# Оценивать
def rate_card_kb(target_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❤️", callback_data=f"rate:like:{target_id}"),
                InlineKeyboardButton(text=lbl(lang, "rate_next"), callback_data=f"rate:skip:{target_id}"),
            ],
            [
                InlineKeyboardButton(text=lbl(lang, "rate_write"), callback_data=f"rate:comment:{target_id}"),
                InlineKeyboardButton(text=lbl(lang, "rate_support"), callback_data=f"rate:support:{target_id}"),
            ],
            [
                InlineKeyboardButton(text="⭐1", callback_data=f"rate:stars:{target_id}:1"),
                InlineKeyboardButton(text="⭐2", callback_data=f"rate:stars:{target_id}:2"),
                InlineKeyboardButton(text="⭐3", callback_data=f"rate:stars:{target_id}:3"),
                InlineKeyboardButton(text="⭐4", callback_data=f"rate:stars:{target_id}:4"),
                InlineKeyboardButton(text="⭐5", callback_data=f"rate:stars:{target_id}:5"),
            ],
            [InlineKeyboardButton(text=lbl(lang, "rate_report"), callback_data=f"rate:report:{target_id}")],
        ]
    )


def rate_after_stars_kb(target_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    """После оценки 1–5 нужно ещё одно действие (ТЗ)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=lbl(lang, "like"), callback_data=f"rate:like:{target_id}"),
                InlineKeyboardButton(text=lbl(lang, "comment"), callback_data=f"rate:comment:{target_id}"),
            ],
            [
                InlineKeyboardButton(text=lbl(lang, "support"), callback_data=f"rate:support:{target_id}"),
                InlineKeyboardButton(text=lbl(lang, "skip"), callback_data=f"rate:skip:{target_id}"),
            ],
        ]
    )


def complaint_reasons_kb(target_id: int, *, kind: str = "user", lang: str = "ru") -> InlineKeyboardMarkup:
    from bot.texts.i18n import COMPLAINT_REASONS, normalize_lang

    reasons = COMPLAINT_REASONS[normalize_lang(lang)]
    prefix = "rate:reason" if kind == "user" else "ev:reason"
    rows = []
    row = []
    for code, label in reasons.items():
        row.append(InlineKeyboardButton(text=label, callback_data=f"{prefix}:{code}:{target_id}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def support_type_kb(target_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=lbl(lang, "anon"), callback_data=f"rate:sup:anon:{target_id}"),
                InlineKeyboardButton(text=lbl(lang, "open"), callback_data=f"rate:sup:open:{target_id}"),
            ]
        ]
    )


def like_offer_kb(from_user_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=lbl(lang, "like_view_yes"), callback_data=f"like:view:{from_user_id}"),
                InlineKeyboardButton(text=lbl(lang, "like_later"), callback_data="like:decline"),
            ]
        ]
    )


def match_dm_kb(url: str, lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=lbl(lang, "write_tg"), url=url)]]
    )


# Цели
def goals_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=lbl(lang, "goal_change"), callback_data="goal:change"),
                InlineKeyboardButton(text=lbl(lang, "goal_withdraw"), callback_data="goal:withdraw"),
            ]
        ]
    )


# Тусовки
def events_menu_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=lbl(lang, "ev_create"), callback_data="ev:create")],
            [InlineKeyboardButton(text=lbl(lang, "ev_my"), callback_data="ev:my")],
            [InlineKeyboardButton(text=lbl(lang, "ev_find"), callback_data="ev:find")],
        ]
    )


def my_events_list_kb(items: list[tuple[int, str]], lang: str = "ru") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label[:64], callback_data=f"ev:pick:{event_id}")]
        for event_id, label in items
    ]
    rows.append([InlineKeyboardButton(text=lbl(lang, "back"), callback_data="ev:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def event_categories_kb(categories: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """categories: [(id, name), ...]"""
    rows = []
    row = []
    for cat_id, name in categories:
        row.append(InlineKeyboardButton(text=name, callback_data=f"ev:cat:{cat_id}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def event_card_kb(event_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=lbl(lang, "ev_apply"), callback_data=f"ev:apply:{event_id}"),
                InlineKeyboardButton(text=lbl(lang, "ev_next"), callback_data=f"ev:next:{event_id}"),
            ],
            [
                InlineKeyboardButton(text=lbl(lang, "ev_share"), callback_data=f"ev:share:{event_id}"),
                InlineKeyboardButton(text=lbl(lang, "ev_report"), callback_data=f"ev:report:{event_id}"),
            ],
        ]
    )


def event_manage_kb(event_id: int, mass_available: bool, lang: str = "ru") -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=lbl(lang, "ev_parts"), callback_data=f"ev:mg:parts:{event_id}"),
            InlineKeyboardButton(text=lbl(lang, "ev_invite"), callback_data=f"ev:mg:invite:{event_id}"),
        ],
        [InlineKeyboardButton(text=lbl(lang, "ev_apps"), callback_data=f"ev:mg:apps:{event_id}")],
        [
            InlineKeyboardButton(text=lbl(lang, "ev_boost_50"), callback_data=f"ev:boost:{event_id}"),
            InlineKeyboardButton(text=lbl(lang, "ev_pin_500"), callback_data=f"ev:pin:{event_id}"),
        ],
        [InlineKeyboardButton(text=lbl(lang, "ev_close_chat"), callback_data=f"ev:mg:close:{event_id}")],
        [InlineKeyboardButton(text=lbl(lang, "ev_edit"), callback_data=f"ev:mg:edit:{event_id}")],
        [InlineKeyboardButton(text=lbl(lang, "ev_delete"), callback_data=f"ev:mg:delask:{event_id}")],
        [InlineKeyboardButton(text=lbl(lang, "back_list"), callback_data="ev:my")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def event_delete_confirm_kb(event_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=lbl(lang, "yes_delete"), callback_data=f"ev:mg:del:{event_id}"),
                InlineKeyboardButton(text=lbl(lang, "cancel"), callback_data=f"ev:mg:back:{event_id}"),
            ]
        ]
    )


def event_close_confirm_kb(event_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=lbl(lang, "yes_close"), callback_data=f"ev:mg:closeok:{event_id}"),
                InlineKeyboardButton(text=lbl(lang, "cancel"), callback_data=f"ev:mg:back:{event_id}"),
            ]
        ]
    )


def event_attending_kb(
    event_id: int,
    *,
    price: int = 0,
    fee_paid: bool = False,
    lang: str = "ru",
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=lbl(lang, "ev_open"), callback_data=f"ev:open:{event_id}"),
            InlineKeyboardButton(text=lbl(lang, "ev_share"), callback_data=f"ev:share:{event_id}"),
        ],
    ]
    if price > 0 and not fee_paid:
        rows.append([
            InlineKeyboardButton(
                text=lbl(lang, "pay_fee").format(price=price),
                callback_data=f"ev:pay:{event_id}",
            )
        ])
    elif price > 0 and fee_paid:
        rows.append([InlineKeyboardButton(text=lbl(lang, "fee_paid"), callback_data="ev:pay:done")])
    rows.append([InlineKeyboardButton(text=lbl(lang, "back_list"), callback_data="ev:my")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def event_pay_confirm_kb(event_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=lbl(lang, "pay_confirm"), callback_data=f"ev:pay:yes:{event_id}"),
                InlineKeyboardButton(text=lbl(lang, "cancel"), callback_data=f"ev:pick:{event_id}"),
            ],
        ]
    )


def event_participants_kb(
  event_id: int,
  participants: list[tuple[str, str]],
  lang: str = "ru",
) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=label[:64], url=url)] for label, url in participants]
    rows.append([InlineKeyboardButton(text=lbl(lang, "back"), callback_data=f"ev:mg:back:{event_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def event_edit_fields_kb(event_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=lbl(lang, "edit_title"), callback_data=f"ev:ed:title:{event_id}"),
                InlineKeyboardButton(text=lbl(lang, "edit_city"), callback_data=f"ev:ed:city:{event_id}"),
            ],
            [
                InlineKeyboardButton(text=lbl(lang, "edit_address"), callback_data=f"ev:ed:address:{event_id}"),
                InlineKeyboardButton(text=lbl(lang, "edit_datetime"), callback_data=f"ev:ed:datetime:{event_id}"),
            ],
            [
                InlineKeyboardButton(text=lbl(lang, "edit_price"), callback_data=f"ev:ed:price:{event_id}"),
                InlineKeyboardButton(text=lbl(lang, "edit_desc"), callback_data=f"ev:ed:description:{event_id}"),
            ],
            [InlineKeyboardButton(text=lbl(lang, "edit_photo"), callback_data=f"ev:ed:photo:{event_id}")],
            [InlineKeyboardButton(text=lbl(lang, "back"), callback_data=f"ev:mg:back:{event_id}")],
        ]
    )


def invite_kb(event_id: int, mass_available: bool, lang: str = "ru") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=lbl(lang, "inv_link"), callback_data=f"ev:inv:link:{event_id}")]]
    if mass_available:
        rows.append([InlineKeyboardButton(text=lbl(lang, "inv_mass"), callback_data=f"ev:inv:mass:{event_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def app_decision_kb(app_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=lbl(lang, "app_accept"), callback_data=f"ev:app:ok:{app_id}"),
                InlineKeyboardButton(text=lbl(lang, "app_reject"), callback_data=f"ev:app:no:{app_id}"),
            ]
        ]
    )


# LUMA
def luma_kb(is_premium: bool, lang: str = "ru") -> InlineKeyboardMarkup:
    if is_premium:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=lbl(lang, "luma_people"), callback_data="luma:people")],
                [InlineKeyboardButton(text=lbl(lang, "luma_events"), callback_data="luma:events")],
                [InlineKeyboardButton(text=lbl(lang, "luma_ask"), callback_data="luma:ask")],
            ]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=lbl(lang, "buy_premium"), callback_data="prof:premium"),
                InlineKeyboardButton(text=lbl(lang, "invite_friends"), callback_data="prof:referral"),
            ]
        ]
    )
