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
    "ru": {"Мужчин": "men", "Женщин": "women"},
    "be": {"Мужчын": "men", "Жанчын": "women"},
    "uk": {"Чоловіків": "men", "Жінок": "women"},
    "kk": {"Ерлерді": "men", "Әйелдерді": "women"},
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
            "<a href='{rules}'>Правила</a>\n\n"
            "Меня зовут Луна, а как зовут тебя?"
        ),
        "REG_ASK_NAME": "Меня зовут Луна, а как зовут тебя?",
        "REG_ASK_PHOTO": "Приятно познакомиться, {name}! Теперь отправь свое фото.",
        "REG_ASK_GENDER": "Великолепно! Теперь мне нужно узнать твой пол",
        "REG_ASK_SEEKING": "Отлично! Кого ты ищешь?",
        "REG_ASK_VISIBLE": "Кому бы ты хотел попадаться в ленте?",
        "REG_ASK_CONTACT": "Мне нужен твой контакт, не беспокойся, другие пользователи его не увидят.",
        "REG_ASK_AGE": "Сколько тебе лет?",
        "REG_ASK_BIO": "Расскажи о себе, хобби/увлечения?",
        "REG_PRIVACY_CITY": "Пользуясь ботом вы соглашаетесь с обработкой персональных данных.\n\nИз какого вы города?",
        "REG_ASK_GOAL": "Есть ли у тебя материальная цель? Расскажи о ней людям, может тебя поддержат)",
        "REG_ASK_GOAL_AMOUNT": "Сколько нужно собрать на эту цель?",
        "REG_PREVIEW_HEADER": "Твоя анкета:",
        "REG_COMPLETE": "Анкета создана! Пройди верификацию в профиле, чтобы открыть полное меню.",
        "MENU_NEED_VERIFY": "Для доступа ко всем разделам пройди верификацию в профиле.",
        "PREMIUM_TEXT": (
            "Premium — переход на новый уровень:\n"
            "• Анкета чаще в топе\n"
            "• Статус Premium в анкете\n"
            "• Рассылка массовых приглашений на вашу тусовку\n"
            "• Поднятие тусовки в топ бесплатно раз в час\n"
            "• Закреп тусовки на час с 50% скидкой\n"
            "• Бесплатный сброс рейтинга раз в месяц"
        ),
        "WITHDRAW_INFO": (
            "Вывод Искр только через Telegram Stars.\n"
            "Минимум: 1000 Искр.\n"
            "Комиссия: 15% (для Premium — 7%).\n\n"
            "После заявки Stars будут отправлены автоматически на ваш аккаунт."
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
        "EVENT_PIN_OK": "Тусовка закреплена на {hours} ч (−{price} Искр).",
        "EVENT_MASS_SENT": "Приглашения отправлены {count} пользователям рядом.",
        "EVENT_NOT_FOUND": "Тусовка не найдена или удалена.",
        "EVENT_DELETED": "Тусовка удалена.",
        "EVENT_DELETE_CONFIRM": "Точно удалить тусовку?",
        "LUMA_INTRO": (
            "Я LUMA — AI-помощник.\n\n"
            "• Поиск людей\n• Поиск тусовок\n• Ответы на вопросы\n"
            "• Помощь организаторам\n\nДоступен с Premium."
        ),
        "LUMA_LIMIT": "Дневной лимит запросов к LUMA исчерпан. Попробуй завтра.",
        "LUMA_ASK": "Напиши запрос LUMA (люди, тусовки или вопрос):",
        "REFERRAL_INTRO": "Приглашай друзей и получай награды!",
        "REFERRAL_INFO": (
            "Награды после создания анкеты приглашённым:\n"
            "1–3 → Premium 1 мес\n"
            "4–5 → Premium 3 мес\n"
            "6–10 → 200 Искр\n"
            "11–100 → 300 Искр + Premium 6 мес\n"
            "100+ → 1000 Искр + Premium навсегда"
        ),
        "BLOGGER_INTRO": (
            "Партнёрская программа для блогеров.\n"
            "Твоя ссылка: {link}\n"
            "Просмотры: {views}\n"
            "Комиссия 20% от покупок рефералов.\n"
            "500 000 просмотров → 1000 Искр\n"
            "1 000 000 просмотров → 2000 Искр"
        ),
        "BLOGGER_PENDING": "Заявка на блогер-программу отправлена. Ожидай подтверждения админа.",
        "LANG_CHANGED": "Язык изменён.",
        "PREMIUM_ACTIVE": "У тебя уже активен Premium ⭐\n\nПодписка действует до: <b>{until}</b>",
        "PREMIUM_TITLE": "Что такое Premium?",
        "PROFILE_DISABLE_CONFIRM": "Вы уверены?",
        "PROFILE_DISABLED_CELEBRATE": "УРААА",
        "PROFILE_DISABLE_GOODBYE": "Мы ждем тебя снова..",
        "BUY_SPARKS_INFO": "Искры — внутренняя валюта для услуг и поддержки других пользователей.\nПополнение: ЮKassa или Telegram Stars.",
        "BUY_SPARKS_RATES": "Курс: 1 Искра = {rub:g} ₽ или {stars:g} Star(s).",
        "PAY_CHOOSE_METHOD": "Выбери способ оплаты для <b>{amount}</b> Искр:",
        "PAY_YOOKASSA_CREATED": "Счёт на <b>{amount}</b> Искр ({rub:.0f} ₽) создан.\nНажми «Оплатить», чтобы перейти к оплате.",
        "PAY_YOOKASSA_STUB": "Счёт на <b>{amount}</b> Искр ({rub:.0f} ₽) создан.\n\n⚠️ ЮKassa в демо-режиме.\nМожно нажать «Симулировать оплату (демо)».",
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
        "BTN_SEND_CONTACT": "Отправить контакт",
        "PROFILE_LANG": "Выбери язык:",
        "VERIFY_INFO": (
            "Запиши кружок с лицом.\nПроизнеси код: <b>{code}</b>\n"
            "Покажи жест: {gesture}\n\nAI проверит лицо, жест и код."
        ),
        "VERIFY_PASSED": "Верификация пройдена! Добро пожаловать в LUMA.",
        "VERIFY_FAILED": "Верификация не пройдена.\n\n{reason}\n\nКод: <b>{code}</b>\nЖест: {gesture}",
        "MODERATION_BLOCKED": "Контент не прошёл модерацию: {reason}",
    },
    "be": {
        "REG_ASK_LANG": "Прывітанне! Абяры мову зносін:",
        "REG_RULES": (
            "Азнаёмцеся з правіламі:\n"
            "<a href='{rules}'>Правілы</a>\n\n"
            "Мяне клічуць Луна, а як цябе?"
        ),
        "REG_ASK_NAME": "Мяне клічуць Луна, а як цябе?",
        "REG_ASK_PHOTO": "Прыемна пазнаёміцца, {name}! Цяпер дашлі сваё фота.",
        "REG_ASK_GENDER": "Выдатна! Які ў цябе пол?",
        "REG_ASK_SEEKING": "Каго ты шукаеш?",
        "REG_ASK_VISIBLE": "Каму паказваць тваю анкету?",
        "REG_ASK_CONTACT": "Мне патрэбны твой кантакт — іншыя яго не ўбачаць.",
        "REG_ASK_AGE": "Колькі табе гадоў?",
        "REG_ASK_BIO": "Раскажы пра сябе, хобі?",
        "REG_PRIVACY_CITY": "Карыстаючыся ботам, вы згаджаецеся на апрацоўку даных.\n\nЗ якога ты горада?",
        "REG_ASK_GOAL": "Ёсць матэрыяльная мэта? Раскажы пра яе.",
        "REG_ASK_GOAL_AMOUNT": "Колькі трэба сабраць на гэтую мэту?",
        "REG_PREVIEW_HEADER": "Твая анкета:",
        "REG_COMPLETE": "Анкета створана! Прайдзі верыфікацыю ў профілі.",
        "MENU_NEED_VERIFY": "Для поўнага доступу прайдзі верыфікацыю ў профілі.",
        "PREMIUM_TEXT": (
            "Premium — новы ўзровень:\n"
            "• Анкета часцей у топе\n"
            "• Статус Premium у анкеце\n"
            "• Масавая рассылка запрашэнняў на тусоўку\n"
            "• Падняцце тусоўкі ў топ бясплатна раз на гадзіну\n"
            "• Замацаванне тусоўкі на гадзіну са зніжкай 50%\n"
            "• Бясплатны скід рэйтынгу раз на месяц"
        ),
        "WITHDRAW_INFO": (
            "Вывад Іскраў толькі праз Telegram Stars.\n"
            "Мінімум: 1000 Іскраў.\n"
            "Камісія: 15% (Premium — 7%).\n\n"
            "Пасля заяўкі Stars будуць адпраўлены аўтаматычна."
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
        "EVENT_PIN_OK": "Закрэплена на {hours} г (−{price} Іскраў).",
        "EVENT_MASS_SENT": "Запрашэнні адпраўлены {count} карыстальнікам.",
        "EVENT_NOT_FOUND": "Тусоўка не знойдзена.",
        "EVENT_DELETED": "Тусоўка выдалена.",
        "EVENT_DELETE_CONFIRM": "Сапраўды выдаліць тусоўку?",
        "LUMA_INTRO": "Я LUMA — AI-памочнік. Пошук людзей і тусовак, адказы, дапамога арганізатарам. Трэба Premium.",
        "LUMA_LIMIT": "Дзённы ліміт LUMA вычарпаны.",
        "LUMA_ASK": "Напішы запыт LUMA:",
        "REFERRAL_INTRO": "Запрашай сяброў і атрымлівай узнагароды!",
        "REFERRAL_INFO": "1–3 → Premium 1 мес\n4–5 → 3 мес\n6–10 → 200 Іскраў\n11–100 → 300 + Premium 6 мес\n100+ → 1000 + Premium назаўжды",
        "BLOGGER_INTRO": "Блогер-праграма.\nСпасылка: {link}\nПрагляды: {views}\nКамісія 20%.",
        "BLOGGER_PENDING": "Заяўка адпраўлена. Чакай пацверджання.",
        "LANG_CHANGED": "Мова зменена.",
        "PREMIUM_ACTIVE": "У цябе ўжо Premium ⭐\n\nДа: <b>{until}</b>",
        "PREMIUM_TITLE": "Што такое Premium?",
        "PROFILE_DISABLE_CONFIRM": "Вы ўпэўнены?",
        "PROFILE_DISABLED_CELEBRATE": "УРААА",
        "PROFILE_DISABLE_GOODBYE": "Мы чакаем цябе зноў..",
        "BUY_SPARKS_INFO": "Іскры — унутраная валюта.\nПапаўненне: ЮKassa або Telegram Stars.",
        "BUY_SPARKS_RATES": "Курс: 1 Іскра = {rub:g} ₽ або {stars:g} Star(s).",
        "PAY_CHOOSE_METHOD": "Абяры спосаб аплаты для <b>{amount}</b> Іскраў:",
        "PAY_YOOKASSA_CREATED": "Рахунак на <b>{amount}</b> Іскраў ({rub:.0f} ₽) створаны.",
        "PAY_YOOKASSA_STUB": "Рахунак на <b>{amount}</b> Іскраў ({rub:.0f} ₽). Дэма-рэжым ЮKassa.",
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
        "BTN_SEND_CONTACT": "Даслаць кантакт",
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
            "<a href='{rules}'>Правила</a>\n\n"
            "Мене звати Луна, а тебе?"
        ),
        "REG_ASK_NAME": "Мене звати Луна, а тебе?",
        "REG_ASK_PHOTO": "Приємно познайомитись, {name}! Тепер надішли своє фото.",
        "REG_ASK_GENDER": "Чудово! Яка у тебе стать?",
        "REG_ASK_SEEKING": "Кого ти шукаєш?",
        "REG_ASK_VISIBLE": "Кому показувати твою анкету?",
        "REG_ASK_CONTACT": "Мені потрібен твій контакт — інші його не побачать.",
        "REG_ASK_AGE": "Скільки тобі років?",
        "REG_ASK_BIO": "Розкажи про себе, хобі?",
        "REG_PRIVACY_CITY": "Користуючись ботом, ви погоджуєтесь на обробку даних.\n\nЗ якого ти міста?",
        "REG_ASK_GOAL": "Є матеріальна ціль? Розкажи про неї.",
        "REG_ASK_GOAL_AMOUNT": "Скільки потрібно зібрати на цю ціль?",
        "REG_PREVIEW_HEADER": "Твоя анкета:",
        "REG_COMPLETE": "Анкету створено! Пройди верифікацію в профілі.",
        "MENU_NEED_VERIFY": "Для повного доступу пройди верифікацію в профілі.",
        "PREMIUM_TEXT": (
            "Premium — новий рівень:\n"
            "• Анкета частіше в топі\n"
            "• Статус Premium в анкеті\n"
            "• Масова розсилка запрошень на тусовку\n"
            "• Підняття тусовки в топ безкоштовно раз на годину\n"
            "• Закріплення тусовки на годину зі знижкою 50%\n"
            "• Безкоштовний скид рейтингу раз на місяць"
        ),
        "WITHDRAW_INFO": (
            "Вивід Іскор тільки через Telegram Stars.\n"
            "Мінімум: 1000 Іскор.\n"
            "Комісія: 15% (Premium — 7%).\n\n"
            "Після заявки Stars будуть надіслані автоматично."
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
        "EVENT_PIN_OK": "Закріплено на {hours} год (−{price} Іскор).",
        "EVENT_MASS_SENT": "Запрошення надіслано {count} користувачам.",
        "EVENT_NOT_FOUND": "Тусовку не знайдено.",
        "EVENT_DELETED": "Тусовку видалено.",
        "EVENT_DELETE_CONFIRM": "Точно видалити тусовку?",
        "LUMA_INTRO": "Я LUMA — AI-помічник. Пошук людей і тусовок, відповіді, допомога організаторам. Потрібен Premium.",
        "LUMA_LIMIT": "Денний ліміт LUMA вичерпано.",
        "LUMA_ASK": "Напиши запит LUMA:",
        "REFERRAL_INTRO": "Запрошуй друзів і отримуй нагороди!",
        "REFERRAL_INFO": "1–3 → Premium 1 міс\n4–5 → 3 міс\n6–10 → 200 Іскор\n11–100 → 300 + Premium 6 міс\n100+ → 1000 + Premium назавжди",
        "BLOGGER_INTRO": "Блогер-програма.\nПосилання: {link}\nПерегляди: {views}\nКомісія 20%.",
        "BLOGGER_PENDING": "Заявку надіслано. Чекай підтвердження.",
        "LANG_CHANGED": "Мову змінено.",
        "PREMIUM_ACTIVE": "У тебе вже є Premium ⭐\n\nДіє до: <b>{until}</b>",
        "PREMIUM_TITLE": "Що таке Premium?",
        "PROFILE_DISABLE_CONFIRM": "Ви впевнені?",
        "PROFILE_DISABLED_CELEBRATE": "УРААА",
        "PROFILE_DISABLE_GOODBYE": "Ми чекаємо на тебе знову..",
        "BUY_SPARKS_INFO": "Іскри — внутрішня валюта.\nПоповнення: ЮKassa або Telegram Stars.",
        "BUY_SPARKS_RATES": "Курс: 1 Іскра = {rub:g} ₽ або {stars:g} Star(s).",
        "PAY_CHOOSE_METHOD": "Обери спосіб оплати для <b>{amount}</b> Іскор:",
        "PAY_YOOKASSA_CREATED": "Рахунок на <b>{amount}</b> Іскор ({rub:.0f} ₽) створено.",
        "PAY_YOOKASSA_STUB": "Рахунок на <b>{amount}</b> Іскор ({rub:.0f} ₽). Демо-режим ЮKassa.",
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
        "BTN_SEND_CONTACT": "Надіслати контакт",
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
            "<a href='{rules}'>Ережелер</a>\n\n"
            "Менің атым Луна, сенікі ше?"
        ),
        "REG_ASK_NAME": "Менің атым Луна, сенікі ше?",
        "REG_ASK_PHOTO": "Танысқаныма қуаныштымын, {name}! Енді фотоңды жібер.",
        "REG_ASK_GENDER": "Керемет! Жынысың қандай?",
        "REG_ASK_SEEKING": "Кімді іздеп жүрсің?",
        "REG_ASK_VISIBLE": "Анкетаңды кімге көрсету керек?",
        "REG_ASK_CONTACT": "Байланысың керек — басқалар оны көрмейді.",
        "REG_ASK_AGE": "Жасың қанша?",
        "REG_ASK_BIO": "Өзің туралы, хоббиің туралы айт?",
        "REG_PRIVACY_CITY": "Ботты пайдалана отырып, деректерді өңдеуге келісесің.\n\nҚай қаладансың?",
        "REG_ASK_GOAL": "Материалдық мақсатың бар ма? Айтып бер.",
        "REG_ASK_GOAL_AMOUNT": "Осы мақсатқа қанша жинау керек?",
        "REG_PREVIEW_HEADER": "Сенің анкетаң:",
        "REG_COMPLETE": "Анкета жасалды! Профильде верификациядан өт.",
        "MENU_NEED_VERIFY": "Толық қолжетімділік үшін профильде верификациядан өт.",
        "PREMIUM_TEXT": (
            "Premium — жаңа деңгей:\n"
            "• Анкета жиі топта\n"
            "• Анкетада Premium мәртебесі\n"
            "• Тусовкаға жаппай шақыру жіберу\n"
            "• Тусовканы сағат сайын тегін топқа көтеру\n"
            "• Тусовканы сағатқа бекіту — 50% жеңілдік\n"
            "• Ай сайын тегін рейтингті тастау"
        ),
        "WITHDRAW_INFO": (
            "Ұшқынды тек Telegram Stars арқылы шығаруға болады.\n"
            "Минимум: 1000 Ұшқын.\n"
            "Комиссия: 15% (Premium — 7%).\n\n"
            "Өтінімнен кейін Stars автоматты түрде жіберіледі."
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
        "EVENT_PIN_OK": "{hours} сағ бекітілді (−{price} Ұшқын).",
        "EVENT_MASS_SENT": "{count} пайдаланушыға шақыру жіберілді.",
        "EVENT_NOT_FOUND": "Тусовка табылмады.",
        "EVENT_DELETED": "Тусовка жойылды.",
        "EVENT_DELETE_CONFIRM": "Тусовканы жоюға сенімдісің бе?",
        "LUMA_INTRO": "Мен LUMA — AI-көмекші. Адамдар мен тусовкаларды іздеу, сұрақтар, ұйымдастырушыға көмек. Premium керек.",
        "LUMA_LIMIT": "LUMA күндік лимиті бітті.",
        "LUMA_ASK": "LUMA-ға сұрау жаз:",
        "REFERRAL_INTRO": "Достарды шақырып, марапат ал!",
        "REFERRAL_INFO": "1–3 → Premium 1 ай\n4–5 → 3 ай\n6–10 → 200 Ұшқын\n11–100 → 300 + Premium 6 ай\n100+ → 1000 + Premium мәңгі",
        "BLOGGER_INTRO": "Блогер бағдарламасы.\nСілтеме: {link}\nҚаралым: {views}\nКомиссия 20%.",
        "BLOGGER_PENDING": "Өтінім жіберілді. Админ растауын күт.",
        "LANG_CHANGED": "Тіл өзгертілді.",
        "PREMIUM_ACTIVE": "Premium белсенді ⭐\n\nМерзімі: <b>{until}</b>",
        "PREMIUM_TITLE": "Premium дегеніміз не?",
        "PROFILE_DISABLE_CONFIRM": "Сенімдісіз бе?",
        "PROFILE_DISABLED_CELEBRATE": "УРААА",
        "PROFILE_DISABLE_GOODBYE": "Қайта күтеміз..",
        "BUY_SPARKS_INFO": "Ұшқын — ішкі валюта.\nТолықтыру: ЮKassa немесе Telegram Stars.",
        "BUY_SPARKS_RATES": "Курс: 1 ұшқын = {rub:g} ₽ немесе {stars:g} Star(s).",
        "PAY_CHOOSE_METHOD": "<b>{amount}</b> ұшқын төлеу әдісін таңдаңыз:",
        "PAY_YOOKASSA_CREATED": "<b>{amount}</b> ұшқын ({rub:.0f} ₽) шоты жасалды.",
        "PAY_YOOKASSA_STUB": "<b>{amount}</b> ұшқын ({rub:.0f} ₽). ЮKassa демо-режимі.",
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
        "BTN_SEND_CONTACT": "Байланысты жіберу",
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
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text


def complaint_reason_label(lang: str, reason_code: str) -> str:
    lang = normalize_lang(lang)
    return COMPLAINT_REASONS.get(lang, COMPLAINT_REASONS["ru"]).get(reason_code, reason_code)


def all_complaint_codes() -> list[str]:
    return list(COMPLAINT_REASONS["ru"].keys())
