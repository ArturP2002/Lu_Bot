"""Мультиязычность бота: ru / be / uk / kk."""

from __future__ import annotations

from typing import Any, Mapping

LANGS = ("ru", "be", "uk", "kk")
DEFAULT_LANG = "ru"

LANG_LABELS = {
    "ru": "Русский",
    "be": "Беларуская",
    "uk": "Українська",
    "kk": "Қазақша",
}

# Кнопки регистрации/профиля по языкам → внутренние коды
GENDER_BUTTONS: dict[str, dict[str, str]] = {
    "ru": {"Мужчина": "male", "Женщина": "female"},
    "be": {"Мужчына": "male", "Жанчына": "female"},
    "uk": {"Чоловік": "male", "Жінка": "female"},
    "kk": {"Ер адам": "male", "Әйел": "female"},
}

SEEKING_BUTTONS: dict[str, dict[str, str]] = {
    "ru": {"Мужчин": "men", "Женщин": "women", "Всех": "both"},
    "be": {"Мужчын": "men", "Жанчын": "women", "Усіх": "both"},
    "uk": {"Чоловіків": "men", "Жінок": "women", "Усіх": "both"},
    "kk": {"Ерлерді": "men", "Әйелдерді": "women", "Барлығын": "both"},
}

VISIBLE_BUTTONS: dict[str, dict[str, str]] = {
    "ru": {"Мужчинам": "men", "Женщинам": "women", "Всем": "all"},
    "be": {"Мужчынам": "men", "Жанчынам": "women", "Усім": "all"},
    "uk": {"Чоловікам": "men", "Жінкам": "women", "Усім": "all"},
    "kk": {"Ерлерге": "men", "Әйелдерге": "women", "Барлығына": "all"},
}

COMPLAINT_REASONS: dict[str, dict[str, str]] = {
    "ru": {
        "fake": "Фейк",
        "fraud": "Мошенничество",
        "ads": "Реклама",
        "porn": "Порно",
        "drugs": "Наркотики",
        "spam": "Спам",
        "insult": "Оскорбления",
        "other": "Другое",
    },
    "be": {
        "fake": "Фэйк",
        "fraud": "Махлярства",
        "ads": "Рэклама",
        "porn": "Порна",
        "drugs": "Наркотыкі",
        "spam": "Спам",
        "insult": "Абразы",
        "other": "Іншае",
    },
    "uk": {
        "fake": "Фейк",
        "fraud": "Шахрайство",
        "ads": "Реклама",
        "porn": "Порно",
        "drugs": "Наркотики",
        "spam": "Спам",
        "insult": "Образи",
        "other": "Інше",
    },
    "kk": {
        "fake": "Жалған",
        "fraud": "Алаяқтық",
        "ads": "Жарнама",
        "porn": "Порно",
        "drugs": "Есірткі",
        "spam": "Спам",
        "insult": "Қорлау",
        "other": "Басқа",
    },
}

# Основные тексты. Ключи совпадают с прежними именами в messages.py
TEXTS: dict[str, dict[str, str]] = {
    "ru": {
        "REG_ASK_LANG": "Привет! Выбери язык общения:",
        "REG_RULES": (
            "Ознакомьтесь с правилами ниже:\n"
            "<a href='{rules}'>Правила</a>"
        ),
        "REG_ASK_NAME": "Меня зовут Луна, а как зовут тебя?",
        "REG_ASK_PHOTO": "Приятно познакомиться, {name}! Отправь фото — можно сразу несколько одним альбомом.",
        "REG_ASK_GENDER": "Великолепно! Теперь мне нужно узнать твой пол",
        "REG_ASK_SEEKING": "Отлично! Кого ты ищешь?",
        "REG_ASK_VISIBLE": "Кому бы ты хотел попадаться в ленте?",
        "REG_ASK_CONTACT": "Мне нужен твой контакт, не беспокойся, другие пользователи его не увидят.",
        "REG_ASK_AGE": "Сколько тебе лет?",
        "REG_ASK_BIO": "Расскажи о себе, хобби/увлечения?\nМожно написать что угодно или пропустить.",
        "REG_PRIVACY_CITY": (
            "Пользуясь ботом вы соглашаетесь с обработкой персональных данных.\n\n"
            "Из какого вы города?\n\n"
            "Можно отправить геолокацию или написать город текстом — так проще искать людей и тусовки рядом. "
            "Город можно изменить в профиле."
        ),
        "REG_ASK_GOAL": "Есть ли у тебя материальная цель? Расскажи о ней людям, может тебя поддержат)",
        "REG_ASK_GOAL_AMOUNT": "Сколько нужно собрать на эту цель?",
        "REG_PREVIEW_HEADER": "Твоя анкета:",
        "REG_COMPLETE": "Анкета создана! Пройди верификацию в профиле, чтобы открыть полное меню.",
        "MENU_NEED_VERIFY": "Для доступа ко всем разделам пройди верификацию в профиле.",
        "PREMIUM_TEXT": (
            "Premium — переход на новый уровень:\n"
            "• Анкета чаще в топе\n"
            "• Статус Premium в анкете\n"
            "• Видео в анкете и дополнительные фото/видео — до 10 файлов\n"
            "• Рассылка массовых приглашений на вашу тусовку\n"
            "• Поднятие тусовки в топ бесплатно раз в час\n"
            "• Закреп тусовки на час со скидкой {pin_discount_pct}%\n"
            "• Бесплатный сброс рейтинга раз в месяц\n"
            "• Комиссия вывода — {withdraw_fee_pct}%\n"
            "• Комиссия поддержки цели — {support_fee_pct}%\n"
            "• Автопродление на 1 месяц с баланса Искр при окончании подписки"
        ),
        "WITHDRAW_INFO": (
            "Вывод Искр через Fragment (Telegram Stars).\n"
            "Минимум: {min} Искр.\n"
            "Комиссия: {fee_pct}% (для Premium — {premium_fee_pct}%).\n"
            "1 искра = 1 Telegram Stars\n\n"
            "Нужен публичный @username в Telegram. Stars отправляются автоматически после заявки."
        ),
        "RATE_EMPTY": "Пока новых анкет нет — загляни чуть позже ✨",
        "RATE_NOT_FOUND": "Эту анкету уже не найти",
        "RATE_COMMENT_HINT": "Напиши комментарий — он уйдёт вместе с лайком 💬",
        "RATE_SUPPORT_HINT": "Поддержи цель анонимно или открыто ⚡",
        "RATE_SUPPORT_AMOUNT": "Сколько Искр отправить? От 10 до 500 000 ⚡",
        "RATE_SUPPORT_AMOUNT_RANGE": "Сумма должна быть от 10 до 500 000 Искр",
        "RATE_REPORT_ASK": "Выбери причину жалобы:",
        "RATE_REPORT_DONE": "Спасибо, жалоба ушла на модерацию 🙏",
        "RATE_STARS_DONE": "Оценка {stars}⭐ принята! Теперь выбери действие:",
        "RATE_AFTER_STARS": "Оценка сохранена. Выполни ещё одно действие или открой следующую анкету.",
        "RATE_SUPPORT_DONE": "Готово! Ты поддержал(а) {name} на {amount} искр ✅",
        "RATE_SUPPORT_NOTIFY_ANON": "Кто-то анонимно поддержал твою цель на {amount} искр ⚡",
        "RATE_SUPPORT_NOTIFY_OPEN": "Тебя открыто поддержали на {amount} искр ⚡\nВот кто решил помочь:",
        "MATCH_MSG": "Ура, взаимный лайк с {name}! ❤️✨\nСамое время написать:",
        "LIKE_NOTIFY": "Кто-то поставил тебе лайк ❤️\nХочешь заглянуть в анкету?",
        "LIKE_COMMENT_NOTIFY": "Тебе лайк с комментарием 💬❤️\n\n«{comment}»\n\nХочешь посмотреть анкету?",
        "LIKE_COMMENT_ON_MATCH": "Кстати, вот что тебе написали:\n«{comment}»",
        "LIKE_VIEW_DECLINED": "Ок, пропускаем 😊",
        "GOAL_CHANGE_NAME": "Какая у тебя новая цель?",
        "GOAL_CHANGE_AMOUNT": "Сколько нужно собрать на эту цель?",
        "GOAL_SHOW": "Цель: {title}\nСобрано: {collected}\nОсталось: {remaining}\nПрогресс: {percent}%",
        "EVENTS_INTRO": "Здесь можно найти компанию и организовать встречи.",
        "EVENT_REPORT_ASK": "Выбери причину жалобы на мероприятие:",
        "EVENT_CLOSE_DONE": (
            "Набор закрыт.\n"
            "Участникам отправлены приглашения в общий чат.\n"
            "Ссылка: {link}"
        ),
        "EVENT_CLOSE_CONFIRM": "Закрыть набор и разослать приглашения участникам?",
        "EVENT_BOOST_OK": "Тусовка поднята в ТОП (−{price} Искр).",
        "EVENT_BOOST_FREE_OK": "Тусовка поднята в ТОП бесплатно (Premium, 1 раз в час).",
        "EVENT_PIN_OK": "Тусовка закреплена на {hours} ч (−{price} Искр).",
        "EVENT_MASS_SENT": "Приглашения отправлены {count} пользователям рядом.",
        "EVENT_NOT_FOUND": "Тусовка не найдена или удалена.",
        "EVENT_DELETED": "Тусовка удалена.",
        "EVENT_DELETE_CONFIRM": "Точно удалить тусовку?",
        "LUMA_INTRO": (
            "Я LU — премиальный AI-консьерж.\n\n"
            "• Точный поиск людей по имени и интересам\n"
            "• Поиск тусовок\n"
            "• Ответы на вопросы по базе LUMA\n"
            "• Помощь организаторам\n\n"
            "Доступен с Premium."
        ),
        "LUMA_LIMIT": "Дневной лимит запросов к LU исчерпан. Попробуй завтра.",
        "LUMA_ASK": "Напиши запрос — имя, интересы, тусовку или вопрос:",
        "REFERRAL_INTRO": "Приглашай друзей и получай награды!",
        "REFERRAL_INFO": (
            "Награды после создания анкеты приглашённым:\n\n"
            "🫡 1–4 приглашённых друга — Premium на 1 месяц.\n\n"
            "🤝 5–9 приглашённых друзей — Premium на 3 месяца.\n\n"
            "🥳 10–24 приглашённых друзей — Premium на 12 месяцев.\n\n"
            "😎 25+ приглашённых друзей — Premium навсегда + статус Блогер "
            "с дополнительными возможностями."
        ),
        "BLOGGER_INTRO": (
            "Партнёрская программа для блогеров.\n"
            "Твоя ссылка: {link}\n"
            "Просмотры: {views}\n"
            "Анкет по ссылке: {profiles}\n"
            "Комиссия 15% от покупок Premium рефералами.\n"
            "За каждые 100 анкет по ссылке → 300 Искр"
        ),
        "BLOGGER_PENDING": "Заявка на блогер-программу отправлена. Ожидай подтверждения админа.",
        "BLOGGER_LOCKED": (
            "Статус Блогер открывается автоматически после 25 приглашённых друзей "
            "(финальный бонус обычной реферальной программы)."
        ),
        "BLOGGER_REVOKED": "Статус Блогер снят администратором. Обратись в поддержку, если это ошибка.",
        "LANG_CHANGED": "Язык изменён.",
        "PREMIUM_ACTIVE": "У тебя уже активен Premium ⭐\n\nПодписка действует до: <b>{until}</b>",
        "PREMIUM_TITLE": "Что такое Premium?",
        "PROFILE_DISABLE_CONFIRM": "Вы уверены?",
        "PROFILE_DISABLED_CELEBRATE": "УРААА",
        "PROFILE_DISABLE_GOODBYE": "Мы ждем тебя снова..",
        "BUY_SPARKS_INFO": "Искры — внутренняя валюта для услуг и поддержки других пользователей.\nПополнение: ЮKassa или Telegram Stars.",
        "BUY_SPARKS_RATES": "Курс: 1 Искра = {rub} ₽ или {stars} Star(s).",
        "PAY_CHOOSE_METHOD": "Выбери способ оплаты для <b>{amount}</b> Искр:",
        "PAY_YOOKASSA_CREATED": "Счёт на <b>{amount}</b> Искр ({rub} ₽) создан.\nНажми «Оплатить», чтобы перейти к оплате.",
        "PAY_YOOKASSA_STUB": "Счёт на <b>{amount}</b> Искр ({rub} ₽) создан.\n\n⚠️ ЮKassa в демо-режиме.\nМожно нажать «Симулировать оплату (демо)».",
        "PAY_SUCCESS": "Зачислено {amount} Искр на баланс!",
        "PAY_PENDING": "Оплата ещё не поступила. Подожди минуту и нажми «Проверить оплату».",
        "PAY_CANCELED": "Платёж отменён. Создай новый счёт через «Купить Искры».",
        "PAY_NOT_FOUND": "Платёж не найден.",
        "PAY_ERROR": "Не удалось создать платёж. Попробуй позже.",
        "RATING_RESET_INFO": "Ты можешь сбросить звёздный рейтинг. С Premium — бесплатно 1 раз в месяц.",
        "VERIFY_CHECKING": "Проверяю кружок… Это займёт несколько секунд.",
        "VERIFY_NEED_PHOTO": "Сначала добавь фото в анкету — без него верификация невозможна.",
        "VERIFY_ERROR": "Не удалось проверить видео. Попробуй отправить кружок ещё раз.",
        "ADMIN_DENIED": "Нет доступа.",
        "ADMIN_URL_MISSING": "Админ URL не настроен.",
        "ADMIN_OPEN": "Админ-панель:",
        "ERR_NOT_ENOUGH_SPARKS": "Недостаточно Искр",
        "ERR_AGE": "Возраст должен быть от 18 лет",
        "ERR_INVALID_INPUT": "Некорректный ввод, попробуй ещё раз",
        "BTN_NEXT_STEP": "Следующий шаг",
        "BTN_SKIP_OPTIONAL": "Пропустить",
        "BTN_MEDIA_DONE": "Готово",
        "BTN_MEDIA_CLEAR": "Очистить",
        "BTN_AGREE_RULES": "Согласен",
        "MEDIA_VIDEO_PREMIUM": "Видео в анкете доступно с Premium. Отправь фото — или несколько фото альбомом.",
        "MEDIA_VIDEO_DROPPED": "Видео сохраняются только с Premium. Фото из альбома записаны.",
        "MEDIA_NEED_FILE": "Отправь фото. С Premium можно также добавить видео.",
        "MEDIA_COUNT": "Сейчас в анкете: {n} из {max}.",
        "MEDIA_ADDED": "Добавлено. Сейчас {n} из {max}. Можно прислать ещё или нажать «Готово».",
        "MEDIA_LIMIT": "Лимит медиагруппы Telegram — {max} файлов. Лишнее не сохранилось.",
        "BTN_SEND_CONTACT": "Отправить контакт",
        "BTN_SEND_LOCATION": "📍 Отправить геолокацию",
        "BTN_MY_CITY": "Мой город",
        "BTN_CITY_YES": "Да, верно",
        "BTN_CITY_RETYPE": "Ввести текстом",
        "GEO_CONFIRM_LOCATION": "Определили город: <b>{city}</b>. Верно?",
        "GEO_CONFIRM_CITY": "Город: <b>{city}</b> (центр на карте). Верно?",
        "GEO_CONFIRM_NO_COORDS": (
            "Не нашли «{city}» на карте. Сохраним как написано — поиск рядом заработает после уточнения. Продолжить?"
        ),
        "GEO_CONFIRM_HINT": "Подтверди город:",
        "GEO_REVERSE_FAIL": "Не удалось определить город по геолокации. Напиши название текстом или попробуй ещё раз.",
        "PROFILE_LANG": "Выбери язык:",
        "VERIFY_INFO": (
            "Запиши кружок с лицом — нужно показать, что ты живой человек.\n"
            "Произнеси код: <b>{code}</b>\n"
            "Покажи жест: {gesture}\n\nAI проверит, что ты живой, жест и код."
        ),
        "VERIFY_PASSED": "Верификация пройдена! Добро пожаловать в LUMA.",
        "VERIFY_FAILED": "Верификация не пройдена.\n\n{reason}\n\nКод: <b>{code}</b>\nЖест: {gesture}",
        "MODERATION_BLOCKED": "Контент не прошёл модерацию: {reason}",
    },
    "be": {
        "REG_ASK_LANG": "Прывітанне! Абяры мову зносін:",
        "REG_RULES": (
            "Азнаёмцеся з правіламі:\n"
            "<a href='{rules}'>Правілы</a>"
        ),
        "REG_ASK_NAME": "Мяне клічуць Луна, а як цябе?",
        "REG_ASK_PHOTO": "Прыемна пазнаёміцца, {name}! Дашлі фота — можна некалькі адным альбомам.",
        "REG_ASK_GENDER": "Выдатна! Які ў цябе пол?",
        "REG_ASK_SEEKING": "Каго ты шукаеш?",
        "REG_ASK_VISIBLE": "Каму паказваць тваю анкету?",
        "REG_ASK_CONTACT": "Мне патрэбны твой кантакт — іншыя яго не ўбачаць.",
        "REG_ASK_AGE": "Колькі табе гадоў?",
        "REG_ASK_BIO": "Раскажы пра сябе, хобі?\nМожна напісаць што заўгодна або прапусціць.",
        "REG_PRIVACY_CITY": (
            "Карыстаючыся ботам, вы згаджаецеся на апрацоўку даных.\n\n"
            "З якога ты горада?\n\n"
            "Можна даслаць геалакацыю або напісаць горад тэкстам. Горад можна змяніць у профілі."
        ),
        "REG_ASK_GOAL": "Ёсць матэрыяльная мэта? Раскажы пра яе.",
        "REG_ASK_GOAL_AMOUNT": "Колькі трэба сабраць на гэтую мэту?",
        "REG_PREVIEW_HEADER": "Твая анкета:",
        "REG_COMPLETE": "Анкета створана! Прайдзі верыфікацыю ў профілі.",
        "MENU_NEED_VERIFY": "Для поўнага доступу прайдзі верыфікацыю ў профілі.",
        "PREMIUM_TEXT": (
            "Premium — новы ўзровень:\n"
            "• Анкета часцей у топе\n"
            "• Статус Premium у анкеце\n"
            "• Відэа ў анкеце і дадатковыя фота/відэа — да 10 файлаў\n"
            "• Масавая рассылка запрашэнняў на тусоўку\n"
            "• Падняцце тусоўкі ў топ бясплатна раз на гадзіну\n"
            "• Замацаванне тусоўкі на гадзіну са зніжкай {pin_discount_pct}%\n"
            "• Бясплатны скід рэйтынгу раз на месяц\n"
            "• Камісія вываду — {withdraw_fee_pct}%\n"
            "• Камісія падтрымкі мэты — {support_fee_pct}%"
        ),
        "WITHDRAW_INFO": (
            "Вывад Іскраў праз Fragment (Telegram Stars).\n"
            "Мінімум: {min} Іскраў.\n"
            "Камісія: {fee_pct}% (Premium — {premium_fee_pct}%).\n"
            "1 іскра = 1 Telegram Stars\n\n"
            "Патрэбны публічны @username у Telegram."
        ),
        "RATE_EMPTY": "Пакуль новых анкет няма ✨",
        "RATE_NOT_FOUND": "Анкета не знойдзена",
        "RATE_COMMENT_HINT": "Напішы каментарый да лайка 💬",
        "RATE_SUPPORT_HINT": "Падтрымай мэту ананімна ці адкрыта ⚡",
        "RATE_SUPPORT_AMOUNT": "Колькі Іскраў адправіць? Ад 10 да 500 000",
        "RATE_SUPPORT_AMOUNT_RANGE": "Сума ад 10 да 500 000 Іскраў",
        "RATE_REPORT_ASK": "Абяры прычыну скаргі:",
        "RATE_REPORT_DONE": "Дзякуй, скарга адпраўлена 🙏",
        "RATE_STARS_DONE": "Ацэнка {stars}⭐ прынята! Цяпер абяры дзеянне:",
        "RATE_AFTER_STARS": "Ацэнка захавана. Зрабі яшчэ адно дзеянне або наступная анкета.",
        "RATE_SUPPORT_DONE": "Гатова! Ты падтрымаў(ла) {name} на {amount} іскраў ✅",
        "RATE_SUPPORT_NOTIFY_ANON": "Хтосьці ананімна падтрымаў тваю мэту на {amount} іскраў ⚡",
        "RATE_SUPPORT_NOTIFY_OPEN": "Цябе адкрыта падтрымалі на {amount} іскраў ⚡",
        "MATCH_MSG": "Узаемны лайк з {name}! ❤️ Напішы:",
        "LIKE_NOTIFY": "Табе паставілі лайк ❤️ Хочаш паглядзець анкету?",
        "LIKE_COMMENT_NOTIFY": "Лайк з каментарыем 💬\n«{comment}»",
        "LIKE_COMMENT_ON_MATCH": "Табе напісалі:\n«{comment}»",
        "LIKE_VIEW_DECLINED": "Добра, прапускаем 😊",
        "GOAL_CHANGE_NAME": "Якая новая мэта?",
        "GOAL_CHANGE_AMOUNT": "Колькі трэба сабраць?",
        "GOAL_SHOW": "Мэта: {title}\nСабрана: {collected}\nЗасталося: {remaining}\nПрагрэс: {percent}%",
        "EVENTS_INTRO": "Тут можна знайсці кампанію і арганізаваць сустрэчы.",
        "EVENT_REPORT_ASK": "Абяры прычыну скаргі на мерапрыемства:",
        "EVENT_CLOSE_DONE": "Набор закрыты. Запрашэнні адпраўлены.\nСпасылка: {link}",
        "EVENT_CLOSE_CONFIRM": "Закрыць набор і разаслаць запрашэнні?",
        "EVENT_BOOST_OK": "Тусоўка ў ТОП (−{price} Іскраў).",
        "EVENT_BOOST_FREE_OK": "Тусоўка ў ТОП бясплатна (Premium, 1 раз на гадзіну).",
        "EVENT_PIN_OK": "Закрэплена на {hours} г (−{price} Іскраў).",
        "EVENT_MASS_SENT": "Запрашэнні адпраўлены {count} карыстальнікам.",
        "EVENT_NOT_FOUND": "Тусоўка не знойдзена.",
        "EVENT_DELETED": "Тусоўка выдалена.",
        "EVENT_DELETE_CONFIRM": "Сапраўды выдаліць тусоўку?",
        "LUMA_INTRO": "Я LU — AI-памочнік. Пошук людзей і тусовак, адказы, дапамога арганізатарам. Трэба Premium.",
        "LUMA_LIMIT": "Дзённы ліміт LUMA вычарпаны.",
        "LUMA_ASK": "Напішы запыт LUMA:",
        "REFERRAL_INTRO": "Запрашай сяброў і атрымлівай узнагароды!",
        "REFERRAL_INFO": (
            "Узнагароды пасля стварэння анкеты:\n\n"
            "🫡 1–4 сяброў — Premium на 1 месяц.\n\n"
            "🤝 5–9 сяброў — Premium на 3 месяцы.\n\n"
            "🥳 10–24 сяброў — Premium на 12 месяцаў.\n\n"
            "😎 25+ сяброў — Premium назаўжды + статус Блогер."
        ),
        "BLOGGER_INTRO": (
            "Блогер-праграма.\n"
            "Спасылка: {link}\n"
            "Прагляды: {views}\n"
            "Анкет па спасылцы: {profiles}\n"
            "Камісія 15% ад пакупак Premium.\n"
            "За кожныя 100 анкет → 300 Іскраў"
        ),
        "BLOGGER_PENDING": "Заяўка адпраўлена. Чакай пацверджання.",
        "BLOGGER_LOCKED": "Статус Блогер адкрываецца аўтаматычна пасля 25 запрошаных сяброў.",
        "BLOGGER_REVOKED": "Статус Блогер зняты адміністратарам.",
        "LANG_CHANGED": "Мова зменена.",
        "PREMIUM_ACTIVE": "У цябе ўжо Premium ⭐\n\nДа: <b>{until}</b>",
        "PREMIUM_TITLE": "Што такое Premium?",
        "PROFILE_DISABLE_CONFIRM": "Вы ўпэўнены?",
        "PROFILE_DISABLED_CELEBRATE": "УРААА",
        "PROFILE_DISABLE_GOODBYE": "Мы чакаем цябе зноў..",
        "BUY_SPARKS_INFO": "Іскры — унутраная валюта.\nПапаўненне: ЮKassa або Telegram Stars.",
        "BUY_SPARKS_RATES": "Курс: 1 Іскра = {rub} ₽ або {stars} Star(s).",
        "PAY_CHOOSE_METHOD": "Абяры спосаб аплаты для <b>{amount}</b> Іскраў:",
        "PAY_YOOKASSA_CREATED": "Рахунак на <b>{amount}</b> Іскраў ({rub} ₽) створаны.",
        "PAY_YOOKASSA_STUB": "Рахунак на <b>{amount}</b> Іскраў ({rub} ₽). Дэма-рэжым ЮKassa.",
        "PAY_SUCCESS": "Залічана {amount} Іскраў!",
        "PAY_PENDING": "Аплата яшчэ не прыйшла. Паспрабуй «Праверыць аплату».",
        "PAY_CANCELED": "Плацёж адменены.",
        "PAY_NOT_FOUND": "Плацёж не знойдзены.",
        "PAY_ERROR": "Не ўдалося стварыць плацёж.",
        "RATING_RESET_INFO": "Можна скінуць рэйтынг. З Premium — бясплатна 1 раз у месяц.",
        "VERIFY_CHECKING": "Правяраю кружок…",
        "VERIFY_NEED_PHOTO": "Спачатку дадай фота ў анкету.",
        "VERIFY_ERROR": "Не ўдалося праверыць відэа. Паспрабуй яшчэ раз.",
        "ADMIN_DENIED": "Няма доступу.",
        "ADMIN_URL_MISSING": "Admin URL не наладжаны.",
        "ADMIN_OPEN": "Адмін-панэль:",
        "ERR_NOT_ENOUGH_SPARKS": "Недастаткова Іскраў",
        "ERR_AGE": "Узрост ад 18 гадоў",
        "ERR_INVALID_INPUT": "Няправільны ўвод",
        "BTN_NEXT_STEP": "Наступны крок",
        "BTN_SKIP_OPTIONAL": "Прапусціць",
        "BTN_MEDIA_DONE": "Гатова",
        "BTN_MEDIA_CLEAR": "Ачысціць",
        "BTN_AGREE_RULES": "Згодны",
        "MEDIA_VIDEO_PREMIUM": "Відэа ў анкеце — з Premium. Дашлі фота або альбом фота.",
        "MEDIA_VIDEO_DROPPED": "Відэа захоўваюцца толькі з Premium. Фота з альбома запісаны.",
        "MEDIA_NEED_FILE": "Дашлі фота. З Premium можна дадаць відэа.",
        "MEDIA_COUNT": "Зараз у анкеце: {n} з {max}.",
        "MEDIA_ADDED": "Дададзена. Зараз {n} з {max}. Можна даслаць яшчэ або націснуць «Гатова».",
        "MEDIA_LIMIT": "Ліміт медыягрупы Telegram — {max} файлаў. Лішняе не захавалася.",
        "BTN_SEND_CONTACT": "Даслаць кантакт",
        "BTN_SEND_LOCATION": "📍 Даслаць геалакацыю",
        "BTN_MY_CITY": "Мой горад",
        "BTN_CITY_YES": "Так, верна",
        "BTN_CITY_RETYPE": "Увесці тэкстам",
        "GEO_CONFIRM_LOCATION": "Вызначылі горад: <b>{city}</b>. Верна?",
        "GEO_CONFIRM_CITY": "Горад: <b>{city}</b> (цэнтр на карце). Верна?",
        "GEO_CONFIRM_NO_COORDS": (
            "Не знайшлі «{city}» на карце. Захаваем як напісана. Працягнуць?"
        ),
        "GEO_CONFIRM_HINT": "Пацвердзі горад:",
        "GEO_REVERSE_FAIL": "Не ўдалося вызначыць горад. Напішы назву тэкстам.",
        "PROFILE_LANG": "Абяры мову:",
        "VERIFY_INFO": "Запішы кружок. Код: <b>{code}</b>\nЖэст: {gesture}",
        "VERIFY_PASSED": "Верыфікацыя прайшла!",
        "VERIFY_FAILED": "Не прайшло.\n{reason}\nКод: <b>{code}</b>\nЖэст: {gesture}",
        "MODERATION_BLOCKED": "Кантэнт не прайшоў мадэрацыю: {reason}",
    },
    "uk": {
        "REG_ASK_LANG": "Привіт! Обери мову спілкування:",
        "REG_RULES": (
            "Ознайомся з правилами:\n"
            "<a href='{rules}'>Правила</a>"
        ),
        "REG_ASK_NAME": "Мене звати Луна, а тебе?",
        "REG_ASK_PHOTO": "Приємно познайомитись, {name}! Надішли фото — можна кілька одним альбомом.",
        "REG_ASK_GENDER": "Чудово! Яка у тебе стать?",
        "REG_ASK_SEEKING": "Кого ти шукаєш?",
        "REG_ASK_VISIBLE": "Кому показувати твою анкету?",
        "REG_ASK_CONTACT": "Мені потрібен твій контакт — інші його не побачать.",
        "REG_ASK_AGE": "Скільки тобі років?",
        "REG_ASK_BIO": "Розкажи про себе, хобі?\nМожна написати що завгодно або пропустити.",
        "REG_PRIVACY_CITY": (
            "Користуючись ботом, ви погоджуєтесь на обробку даних.\n\n"
            "З якого ти міста?\n\n"
            "Можна надіслати геолокацію або написати місто текстом. Місто можна змінити в профілі."
        ),
        "REG_ASK_GOAL": "Є матеріальна ціль? Розкажи про неї.",
        "REG_ASK_GOAL_AMOUNT": "Скільки потрібно зібрати на цю ціль?",
        "REG_PREVIEW_HEADER": "Твоя анкета:",
        "REG_COMPLETE": "Анкету створено! Пройди верифікацію в профілі.",
        "MENU_NEED_VERIFY": "Для повного доступу пройди верифікацію в профілі.",
        "PREMIUM_TEXT": (
            "Premium — новий рівень:\n"
            "• Анкета частіше в топі\n"
            "• Статус Premium в анкеті\n"
            "• Відео в анкеті та додаткові фото/відео — до 10 файлів\n"
            "• Масова розсилка запрошень на тусовку\n"
            "• Підняття тусовки в топ безкоштовно раз на годину\n"
            "• Закріплення тусовки на годину зі знижкою {pin_discount_pct}%\n"
            "• Безкоштовний скид рейтингу раз на місяць\n"
            "• Комісія виводу — {withdraw_fee_pct}%\n"
            "• Комісія підтримки цілі — {support_fee_pct}%"
        ),
        "WITHDRAW_INFO": (
            "Вивід Іскор через Fragment (Telegram Stars).\n"
            "Мінімум: {min} Іскор.\n"
            "Комісія: {fee_pct}% (Premium — {premium_fee_pct}%).\n"
            "1 іскра = 1 Telegram Stars\n\n"
            "Потрібен публічний @username в Telegram."
        ),
        "RATE_EMPTY": "Поки нових анкет немає ✨",
        "RATE_NOT_FOUND": "Анкету не знайдено",
        "RATE_COMMENT_HINT": "Напиши коментар до лайку 💬",
        "RATE_SUPPORT_HINT": "Підтримай ціль анонімно або відкрито ⚡",
        "RATE_SUPPORT_AMOUNT": "Скільки Іскор надіслати? Від 10 до 500 000",
        "RATE_SUPPORT_AMOUNT_RANGE": "Сума від 10 до 500 000 Іскор",
        "RATE_REPORT_ASK": "Обери причину скарги:",
        "RATE_REPORT_DONE": "Дякуємо, скаргу надіслано 🙏",
        "RATE_STARS_DONE": "Оцінку {stars}⭐ прийнято! Тепер обери дію:",
        "RATE_AFTER_STARS": "Оцінку збережено. Зроби ще одну дію або наступна анкета.",
        "RATE_SUPPORT_DONE": "Готово! Ти підтримав(ла) {name} на {amount} іскор ✅",
        "RATE_SUPPORT_NOTIFY_ANON": "Хтось анонімно підтримав твою ціль на {amount} іскор ⚡",
        "RATE_SUPPORT_NOTIFY_OPEN": "Тебе відкрито підтримали на {amount} іскор ⚡",
        "MATCH_MSG": "Взаємний лайк з {name}! ❤️ Напиши:",
        "LIKE_NOTIFY": "Тобі поставили лайк ❤️ Хочеш подивитись анкету?",
        "LIKE_COMMENT_NOTIFY": "Лайк з коментарем 💬\n«{comment}»",
        "LIKE_COMMENT_ON_MATCH": "Тобі написали:\n«{comment}»",
        "LIKE_VIEW_DECLINED": "Ок, пропускаємо 😊",
        "GOAL_CHANGE_NAME": "Яка нова ціль?",
        "GOAL_CHANGE_AMOUNT": "Скільки потрібно зібрати?",
        "GOAL_SHOW": "Ціль: {title}\nЗібрано: {collected}\nЗалишилось: {remaining}\nПрогрес: {percent}%",
        "EVENTS_INTRO": "Тут можна знайти компанію та організувати зустрічі.",
        "EVENT_REPORT_ASK": "Обери причину скарги на подію:",
        "EVENT_CLOSE_DONE": "Набір закрито. Запрошення надіслано.\nПосилання: {link}",
        "EVENT_CLOSE_CONFIRM": "Закрити набір і розіслати запрошення?",
        "EVENT_BOOST_OK": "Тусовку піднято в ТОП (−{price} Іскор).",
        "EVENT_BOOST_FREE_OK": "Тусовку піднято в ТОП безкоштовно (Premium, 1 раз на годину).",
        "EVENT_PIN_OK": "Закріплено на {hours} год (−{price} Іскор).",
        "EVENT_MASS_SENT": "Запрошення надіслано {count} користувачам.",
        "EVENT_NOT_FOUND": "Тусовку не знайдено.",
        "EVENT_DELETED": "Тусовку видалено.",
        "EVENT_DELETE_CONFIRM": "Точно видалити тусовку?",
        "LUMA_INTRO": "Я LU — AI-помічник. Пошук людей і тусовок, відповіді, допомога організаторам. Потрібен Premium.",
        "LUMA_LIMIT": "Денний ліміт LUMA вичерпано.",
        "LUMA_ASK": "Напиши запит LUMA:",
        "REFERRAL_INTRO": "Запрошуй друзів і отримуй нагороди!",
        "REFERRAL_INFO": (
            "Нагороди після створення анкети:\n\n"
            "🫡 1–4 друзів — Premium на 1 місяць.\n\n"
            "🤝 5–9 друзів — Premium на 3 місяці.\n\n"
            "🥳 10–24 друзів — Premium на 12 місяців.\n\n"
            "😎 25+ друзів — Premium назавжди + статус Блогер."
        ),
        "BLOGGER_INTRO": (
            "Блогер-програма.\n"
            "Посилання: {link}\n"
            "Перегляди: {views}\n"
            "Анкет за посиланням: {profiles}\n"
            "Комісія 15% від покупок Premium.\n"
            "За кожні 100 анкет → 300 Іскор"
        ),
        "BLOGGER_PENDING": "Заявку надіслано. Чекай підтвердження.",
        "BLOGGER_LOCKED": "Статус Блогер відкривається автоматично після 25 запрошених друзів.",
        "BLOGGER_REVOKED": "Статус Блогер знято адміністратором.",
        "LANG_CHANGED": "Мову змінено.",
        "PREMIUM_ACTIVE": "У тебе вже є Premium ⭐\n\nДіє до: <b>{until}</b>",
        "PREMIUM_TITLE": "Що таке Premium?",
        "PROFILE_DISABLE_CONFIRM": "Ви впевнені?",
        "PROFILE_DISABLED_CELEBRATE": "УРААА",
        "PROFILE_DISABLE_GOODBYE": "Ми чекаємо на тебе знову..",
        "BUY_SPARKS_INFO": "Іскри — внутрішня валюта.\nПоповнення: ЮKassa або Telegram Stars.",
        "BUY_SPARKS_RATES": "Курс: 1 Іскра = {rub} ₽ або {stars} Star(s).",
        "PAY_CHOOSE_METHOD": "Обери спосіб оплати для <b>{amount}</b> Іскор:",
        "PAY_YOOKASSA_CREATED": "Рахунок на <b>{amount}</b> Іскор ({rub} ₽) створено.",
        "PAY_YOOKASSA_STUB": "Рахунок на <b>{amount}</b> Іскор ({rub} ₽). Демо-режим ЮKassa.",
        "PAY_SUCCESS": "Зараховано {amount} Іскор!",
        "PAY_PENDING": "Оплата ще не надійшла. Натисни «Перевірити оплату».",
        "PAY_CANCELED": "Платіж скасовано.",
        "PAY_NOT_FOUND": "Платіж не знайдено.",
        "PAY_ERROR": "Не вдалося створити платіж.",
        "RATING_RESET_INFO": "Можна скинути рейтинг. З Premium — безкоштовно 1 раз на місяць.",
        "VERIFY_CHECKING": "Перевіряю кружок…",
        "VERIFY_NEED_PHOTO": "Спочатку додай фото в анкету.",
        "VERIFY_ERROR": "Не вдалося перевірити відео. Спробуй ще раз.",
        "ADMIN_DENIED": "Немає доступу.",
        "ADMIN_URL_MISSING": "Admin URL не налаштований.",
        "ADMIN_OPEN": "Адмін-панель:",
        "ERR_NOT_ENOUGH_SPARKS": "Недостатньо Іскор",
        "ERR_AGE": "Вік від 18 років",
        "ERR_INVALID_INPUT": "Некоректне введення",
        "BTN_NEXT_STEP": "Наступний крок",
        "BTN_SKIP_OPTIONAL": "Пропустити",
        "BTN_MEDIA_DONE": "Готово",
        "BTN_MEDIA_CLEAR": "Очистити",
        "BTN_AGREE_RULES": "Погоджуюсь",
        "MEDIA_VIDEO_PREMIUM": "Відео в анкеті доступне з Premium. Надішли фото або альбом фото.",
        "MEDIA_VIDEO_DROPPED": "Відео зберігаються лише з Premium. Фото з альбому записані.",
        "MEDIA_NEED_FILE": "Надішли фото. З Premium можна додати відео.",
        "MEDIA_COUNT": "Зараз в анкеті: {n} з {max}.",
        "MEDIA_ADDED": "Додано. Зараз {n} з {max}. Можна надіслати ще або натиснути «Готово».",
        "MEDIA_LIMIT": "Ліміт медіагрупи Telegram — {max} файлів. Зайве не збереглося.",
        "BTN_SEND_CONTACT": "Надіслати контакт",
        "BTN_SEND_LOCATION": "📍 Надіслати геолокацію",
        "BTN_MY_CITY": "Моє місто",
        "BTN_CITY_YES": "Так, вірно",
        "BTN_CITY_RETYPE": "Ввести текстом",
        "GEO_CONFIRM_LOCATION": "Визначили місто: <b>{city}</b>. Вірно?",
        "GEO_CONFIRM_CITY": "Місто: <b>{city}</b> (центр на карті). Вірно?",
        "GEO_CONFIRM_NO_COORDS": (
            "Не знайшли «{city}» на карті. Збережемо як написано. Продовжити?"
        ),
        "GEO_CONFIRM_HINT": "Підтверди місто:",
        "GEO_REVERSE_FAIL": "Не вдалося визначити місто. Напиши назву текстом.",
        "PROFILE_LANG": "Обери мову:",
        "VERIFY_INFO": "Запиши кружок. Код: <b>{code}</b>\nЖест: {gesture}",
        "VERIFY_PASSED": "Верифікацію пройдено!",
        "VERIFY_FAILED": "Не пройдено.\n{reason}\nКод: <b>{code}</b>\nЖест: {gesture}",
        "MODERATION_BLOCKED": "Контент не пройшов модерацію: {reason}",
    },
    "kk": {
        "REG_ASK_LANG": "Сәлем! Тілді таңда:",
        "REG_RULES": (
            "Ережелермен таныс:\n"
            "<a href='{rules}'>Ережелер</a>"
        ),
        "REG_ASK_NAME": "Менің атым Луна, сенікі ше?",
        "REG_ASK_PHOTO": "Танысқаныма қуаныштымын, {name}! Фото жібер — бір альбоммен бірнешеуін жіберуге болады.",
        "REG_ASK_GENDER": "Керемет! Жынысың қандай?",
        "REG_ASK_SEEKING": "Кімді іздеп жүрсің?",
        "REG_ASK_VISIBLE": "Анкетаңды кімге көрсету керек?",
        "REG_ASK_CONTACT": "Байланысың керек — басқалар оны көрмейді.",
        "REG_ASK_AGE": "Жасың қанша?",
        "REG_ASK_BIO": "Өзің туралы, хоббиің туралы айт?\nКез келген мәтінді жазуға немесе өткізіп жіберуге болады.",
        "REG_PRIVACY_CITY": (
            "Ботты пайдалана отырып, деректерді өңдеуге келісесің.\n\n"
            "Қай қаладансың?\n\n"
            "Геолокация жіберуге немесе қаланы жазуға болады. Қаланы профильде өзгертуге болады."
        ),
        "REG_ASK_GOAL": "Материалдық мақсатың бар ма? Айтып бер.",
        "REG_ASK_GOAL_AMOUNT": "Осы мақсатқа қанша жинау керек?",
        "REG_PREVIEW_HEADER": "Сенің анкетаң:",
        "REG_COMPLETE": "Анкета жасалды! Профильде верификациядан өт.",
        "MENU_NEED_VERIFY": "Толық қолжетімділік үшін профильде верификациядан өт.",
        "PREMIUM_TEXT": (
            "Premium — жаңа деңгей:\n"
            "• Анкета жиі топта\n"
            "• Анкетада Premium мәртебесі\n"
            "• Анкетада видео және қосымша фото/видео — 10 файлға дейін\n"
            "• Тусовкаға жаппай шақыру жіберу\n"
            "• Тусовканы сағат сайын тегін топқа көтеру\n"
            "• Тусовканы сағатқа бекіту — {pin_discount_pct}% жеңілдік\n"
            "• Ай сайын тегін рейтингті тастау\n"
            "• Шығару комиссиясы — {withdraw_fee_pct}%\n"
            "• Мақсатты қолдау комиссиясы — {support_fee_pct}%"
        ),
        "WITHDRAW_INFO": (
            "Ұшқынды Fragment арқылы шығару (Telegram Stars).\n"
            "Минимум: {min} Ұшқын.\n"
            "Комиссия: {fee_pct}% (Premium — {premium_fee_pct}%).\n"
            "1 ұшқын = 1 Telegram Stars\n\n"
            "Telegram-дағы @username қажет."
        ),
        "RATE_EMPTY": "Әзірге жаңа анкета жоқ ✨",
        "RATE_NOT_FOUND": "Анкета табылмады",
        "RATE_COMMENT_HINT": "Лайкпен бірге пікір жаз 💬",
        "RATE_SUPPORT_HINT": "Мақсатты аноним немесе ашық қолда ⚡",
        "RATE_SUPPORT_AMOUNT": "Қанша Ұшқын жіберу керек? 10–500 000",
        "RATE_SUPPORT_AMOUNT_RANGE": "Сома 10–500 000 Ұшқын аралығында",
        "RATE_REPORT_ASK": "Шағым себебін таңда:",
        "RATE_REPORT_DONE": "Рақмет, шағым модерацияға кетті 🙏",
        "RATE_STARS_DONE": "Баға {stars}⭐ қабылданды! Енді әрекетті таңда:",
        "RATE_AFTER_STARS": "Баға сақталды. Тағы бір әрекет жаса немесе келесі анкета.",
        "RATE_SUPPORT_DONE": "Дайын! {name} үшін {amount} ұшқын ✅",
        "RATE_SUPPORT_NOTIFY_ANON": "Біреу аноним түрде мақсатыңды {amount} ұшқынмен қолдады ⚡",
        "RATE_SUPPORT_NOTIFY_OPEN": "Сені ашық қолдады: {amount} ұшқын ⚡",
        "MATCH_MSG": "{name}мен өзара лайк! ❤️ Жаз:",
        "LIKE_NOTIFY": "Саған лайк қойды ❤️ Анкетаны көргің келе ме?",
        "LIKE_COMMENT_NOTIFY": "Пікірлі лайк 💬\n«{comment}»",
        "LIKE_COMMENT_ON_MATCH": "Саған жазды:\n«{comment}»",
        "LIKE_VIEW_DECLINED": "Жарайды, өткіземіз 😊",
        "GOAL_CHANGE_NAME": "Жаңа мақсат қандай?",
        "GOAL_CHANGE_AMOUNT": "Қанша жинау керек?",
        "GOAL_SHOW": "Мақсат: {title}\nЖиналды: {collected}\nҚалды: {remaining}\nПрогресс: {percent}%",
        "EVENTS_INTRO": "Мұнда компания тауып, кездесулер ұйымдастыруға болады.",
        "EVENT_REPORT_ASK": "Іс-шараға шағым себебін таңда:",
        "EVENT_CLOSE_DONE": "Жинақ жабылды. Шақырулар жіберілді.\nСілтеме: {link}",
        "EVENT_CLOSE_CONFIRM": "Жинақты жауып, шақыруларды жібереміз бе?",
        "EVENT_BOOST_OK": "Тусовка ТОП-қа көтерілді (−{price} Ұшқын).",
        "EVENT_BOOST_FREE_OK": "Тусовка тегін ТОП-қа көтерілді (Premium, сағатына 1 рет).",
        "EVENT_PIN_OK": "{hours} сағ бекітілді (−{price} Ұшқын).",
        "EVENT_MASS_SENT": "{count} пайдаланушыға шақыру жіберілді.",
        "EVENT_NOT_FOUND": "Тусовка табылмады.",
        "EVENT_DELETED": "Тусовка жойылды.",
        "EVENT_DELETE_CONFIRM": "Тусовканы жоюға сенімдісің бе?",
        "LUMA_INTRO": "Мен LU — AI-көмекші. Адамдар мен тусовкаларды іздеу, сұрақтар, ұйымдастырушыға көмек. Premium керек.",
        "LUMA_LIMIT": "LUMA күндік лимиті бітті.",
        "LUMA_ASK": "LUMA-ға сұрау жаз:",
        "REFERRAL_INTRO": "Достарды шақырып, марапат ал!",
        "REFERRAL_INFO": (
            "Марапаттар анкета жасалғаннан кейін:\n\n"
            "🫡 1–4 дос — Premium 1 айға.\n\n"
            "🤝 5–9 дос — Premium 3 айға.\n\n"
            "🥳 10–24 дос — Premium 12 айға.\n\n"
            "😎 25+ дос — Premium мәңгі + Блогер мәртебесі."
        ),
        "BLOGGER_INTRO": (
            "Блогер бағдарламасы.\n"
            "Сілтеме: {link}\n"
            "Қаралым: {views}\n"
            "Сілтеме бойынша анкета: {profiles}\n"
            "Premium сатып алудан комиссия 15%.\n"
            "Әр 100 анкета үшін → 300 Ұшқын"
        ),
        "BLOGGER_PENDING": "Өтінім жіберілді. Админ растауын күт.",
        "BLOGGER_LOCKED": "Блогер мәртебесі 25 шақырылған достан кейін автоматты ашылады.",
        "BLOGGER_REVOKED": "Блогер мәртебесін әкімші алып тастады.",
        "LANG_CHANGED": "Тіл өзгертілді.",
        "PREMIUM_ACTIVE": "Premium белсенді ⭐\n\nМерзімі: <b>{until}</b>",
        "PREMIUM_TITLE": "Premium дегеніміз не?",
        "PROFILE_DISABLE_CONFIRM": "Сенімдісіз бе?",
        "PROFILE_DISABLED_CELEBRATE": "УРААА",
        "PROFILE_DISABLE_GOODBYE": "Қайта күтеміз..",
        "BUY_SPARKS_INFO": "Ұшқын — ішкі валюта.\nТолықтыру: ЮKassa немесе Telegram Stars.",
        "BUY_SPARKS_RATES": "Курс: 1 ұшқын = {rub} ₽ немесе {stars} Star(s).",
        "PAY_CHOOSE_METHOD": "<b>{amount}</b> ұшқын төлеу әдісін таңдаңыз:",
        "PAY_YOOKASSA_CREATED": "<b>{amount}</b> ұшқын ({rub} ₽) шоты жасалды.",
        "PAY_YOOKASSA_STUB": "<b>{amount}</b> ұшқын ({rub} ₽). ЮKassa демо-режимі.",
        "PAY_SUCCESS": "{amount} ұшқын есептелді!",
        "PAY_PENDING": "Төлем әлі келмеді. «Төлемді тексеру» басыңыз.",
        "PAY_CANCELED": "Төлем болдырылмады.",
        "PAY_NOT_FOUND": "Төлем табылмады.",
        "PAY_ERROR": "Төлем жасау сәтсіз.",
        "RATING_RESET_INFO": "Рейтингті тастауға болады. Premium — айына 1 рет тегін.",
        "VERIFY_CHECKING": "Дөңгелекті тексеруде…",
        "VERIFY_NEED_PHOTO": "Алдымен анкетаға фото қосыңыз.",
        "VERIFY_ERROR": "Бейнені тексеру сәтсіз. Қайта жіберіңіз.",
        "ADMIN_DENIED": "Қолжетімсіз.",
        "ADMIN_URL_MISSING": "Admin URL бапталмаған.",
        "ADMIN_OPEN": "Админ-панель:",
        "ERR_NOT_ENOUGH_SPARKS": "Ұшқын жеткіліксіз",
        "ERR_AGE": "Жас 18-ден бастап",
        "ERR_INVALID_INPUT": "Қате енгізу",
        "BTN_NEXT_STEP": "Келесі қадам",
        "BTN_SKIP_OPTIONAL": "Өткізіп жіберу",
        "BTN_MEDIA_DONE": "Дайын",
        "BTN_MEDIA_CLEAR": "Тазалау",
        "BTN_AGREE_RULES": "Келісемін",
        "MEDIA_VIDEO_PREMIUM": "Анкетадағы видео — Premium-мен. Фото немесе фото альбомын жібер.",
        "MEDIA_VIDEO_DROPPED": "Видео тек Premium-де сақталады. Альбомдағы фото жазылды.",
        "MEDIA_NEED_FILE": "Фото жібер. Premium-мен видео қосуға болады.",
        "MEDIA_COUNT": "Анкетада қазір: {n} / {max}.",
        "MEDIA_ADDED": "Қосылды. Қазір {n} / {max}. Тағы жіберуге немесе «Дайын» басуға болады.",
        "MEDIA_LIMIT": "Telegram медиатоп шегі — {max} файл. Артығы сақталмады.",
        "BTN_SEND_CONTACT": "Байланысты жіберу",
        "BTN_SEND_LOCATION": "📍 Геолокация жіберу",
        "BTN_MY_CITY": "Менің қалам",
        "BTN_CITY_YES": "Иә, дұрыс",
        "BTN_CITY_RETYPE": "Мәтінмен енгізу",
        "GEO_CONFIRM_LOCATION": "Қала: <b>{city}</b>. Дұрыс па?",
        "GEO_CONFIRM_CITY": "Қала: <b>{city}</b> (картадағы орталық). Дұрыс па?",
        "GEO_CONFIRM_NO_COORDS": (
            "«{city}» картадан табылмады. Жазылғандай сақтаймыз. Жалғастыру?"
        ),
        "GEO_CONFIRM_HINT": "Қаланы растаңыз:",
        "GEO_REVERSE_FAIL": "Қаланы анықтау сәтсіз. Атын жазыңыз.",
        "PROFILE_LANG": "Тілді таңда:",
        "VERIFY_INFO": "Дөңгелек жаз. Код: <b>{code}</b>\nИшара: {gesture}",
        "VERIFY_PASSED": "Верификация өтті!",
        "VERIFY_FAILED": "Өтпеді.\n{reason}\nКод: <b>{code}</b>\nИшара: {gesture}",
        "MODERATION_BLOCKED": "Контент модерациядан өтпеді: {reason}",
    },
}


def normalize_lang(lang: str | None) -> str:
    if not lang:
        return DEFAULT_LANG
    lang = lang.lower().strip()
    return lang if lang in LANGS else DEFAULT_LANG


def lang_of(user: Any | None) -> str:
    if user is None:
        return DEFAULT_LANG
    return normalize_lang(getattr(user, "language", None) or DEFAULT_LANG)


def t(lang_or_user: Any, key: str, **kwargs: Any) -> str:
    """Получить перевод. Первый аргумент — язык (str) или User."""
    if isinstance(lang_or_user, str):
        lang = normalize_lang(lang_or_user)
    else:
        lang = lang_of(lang_or_user)
    bucket = TEXTS.get(lang) or TEXTS[DEFAULT_LANG]
    text = bucket.get(key) or TEXTS[DEFAULT_LANG].get(key) or key
    if kwargs:
        # Экранируем { } в значениях, иначе reason от ИИ с скобками ломает str.format
        safe = {
            k: str(v).replace("{", "{{").replace("}", "}}") if v is not None else ""
            for k, v in kwargs.items()
        }
        try:
            return text.format(**safe)
        except (KeyError, ValueError, IndexError):
            return text
    return text


def complaint_reason_label(lang: str, reason_code: str) -> str:
    lang = normalize_lang(lang)
    return COMPLAINT_REASONS.get(lang, COMPLAINT_REASONS["ru"]).get(reason_code, reason_code)


def all_complaint_codes() -> list[str]:
    return list(COMPLAINT_REASONS["ru"].keys())
