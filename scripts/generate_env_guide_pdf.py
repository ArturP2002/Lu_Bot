#!/usr/bin/env python3
"""Генерация PDF-инструкции по работе с .env на сервере LUMO."""

from pathlib import Path

from fpdf import FPDF

FONT_PATH = "/Library/Fonts/Arial Unicode.ttf"
OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "LUMO_Инструкция_Работа_На_Сервере.pdf"


class GuidePDF(FPDF):
    def __init__(self) -> None:
        super().__init__()
        self.add_font("Main", "", FONT_PATH)
        self.add_font("Main", "B", FONT_PATH)
        self.set_auto_page_break(auto=True, margin=18)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Main", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"LUMO — инструкция для администратора  |  Страница {self.page_no()}", align="C")

    def cover(self) -> None:
        self.add_page()
        self.set_font("Main", "B", 22)
        self.ln(35)
        self.cell(0, 12, "LUMO Bot", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_font("Main", "B", 16)
        self.cell(0, 10, "Инструкция по настройке .env", align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 10, "и обновлению на сервере", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(12)
        self.set_font("Main", "", 11)
        self.set_text_color(60, 60, 60)
        self.multi_cell(0, 7, "Как подключиться к серверу, изменить ключи и параметры в файле конфигурации, а также установить обновления проекта.", align="C")
        self.ln(20)
        self.set_text_color(0, 0, 0)
        self.set_font("Main", "B", 11)
        self.cell(0, 8, "Сервер:", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Main", "", 11)
        self.cell(0, 8, "45.91.237.133", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_font("Main", "B", 11)
        self.cell(0, 8, "Путь к проекту:", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Main", "", 11)
        self.cell(0, 8, "/opt/lu_bot", new_x="LMARGIN", new_y="NEXT")

    def h1(self, text: str) -> None:
        self.ln(4)
        self.set_font("Main", "B", 14)
        self.set_text_color(20, 60, 120)
        self.multi_cell(0, 8, text)
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def h2(self, text: str) -> None:
        self.ln(2)
        self.set_font("Main", "B", 11)
        self.multi_cell(0, 7, text)
        self.ln(1)

    def p(self, text: str) -> None:
        self.set_font("Main", "", 10)
        self.multi_cell(0, 6, text)
        self.ln(1)

    def bullet(self, text: str) -> None:
        self.set_font("Main", "", 10)
        self.set_x(self.l_margin)
        self.multi_cell(0, 6, f"- {text}")

    def code_block(self, text: str) -> None:
        self.set_fill_color(245, 245, 245)
        self.set_font("Main", "", 9)
        for line in text.strip().split("\n"):
            self.cell(0, 5.5, f"  {line}", new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(2)

    def table_row(self, col1: str, col2: str, header: bool = False) -> None:
        if header:
            self.set_font("Main", "B", 9)
            self.set_fill_color(230, 236, 245)
        else:
            self.set_font("Main", "", 9)
            self.set_fill_color(250, 250, 250)
        w1, w2 = 55, 125
        x0 = self.l_margin
        y0 = self.get_y()
        if y0 > self.page_break_trigger:
            self.add_page()
            y0 = self.get_y()
        self.set_xy(x0, y0)
        self.multi_cell(w1, 5.5, col1, border=1, fill=True)
        y1 = self.get_y()
        self.set_xy(x0 + w1, y0)
        self.multi_cell(w2, 5.5, col2, border=1, fill=True)
        y2 = self.get_y()
        self.set_xy(x0, max(y1, y2))
        self.ln(0)

    def warning(self, text: str) -> None:
        self.set_fill_color(255, 248, 220)
        self.set_font("Main", "B", 10)
        self.set_x(self.l_margin)
        self.multi_cell(0, 6, f"[!] {text}", fill=True)
        self.ln(1)


def build() -> None:
    pdf = GuidePDF()
    pdf.cover()

    # 1. Введение
    pdf.add_page()
    pdf.h1("1. О чём эта инструкция")
    pdf.p(
        "Проект LUMO (Telegram-бот и админ-панель) работает на выделенном сервере. "
        "Все секретные ключи, токены и адреса сервисов хранятся в файле .env в папке проекта."
    )
    pdf.p(
        "Этот документ описывает: как зайти на сервер, открыть .env, изменить нужные параметры, "
        "сохранить изменения и перезапустить бота."
    )
    pdf.warning(
        "Храните пароль от сервера и содержимое .env в безопасном месте. Не отправляйте их в открытых чатах и не публикуйте в интернете."
    )

    # 2. Данные для входа
    pdf.h1("2. Данные для подключения к серверу")
    pdf.table_row("Параметр", "Значение", header=True)
    pdf.table_row("IP-адрес", "45.91.237.133")
    pdf.table_row("Пользователь", "root")
    pdf.table_row("Пароль", "rFbUTevAX_z9@j")
    pdf.table_row("Папка проекта", "/opt/lu_bot")
    pdf.table_row("Файл настроек", "/opt/lu_bot/.env")
    pdf.ln(3)
    pdf.p("Подключение выполняется по протоколу SSH — защищённому удалённому доступу к командной строке сервера.")

    # 3. Подключение с Mac
    pdf.h1("3. Подключение к серверу (macOS)")
    pdf.h2("Шаг 1. Откройте «Терминал»")
    pdf.p("Нажмите Cmd + Пробел, введите «Terminal» и откройте приложение.")
    pdf.h2("Шаг 2. Введите команду подключения")
    pdf.code_block("ssh root@45.91.237.133")
    pdf.h2("Шаг 3. Подтвердите подключение")
    pdf.p("При первом входе система спросит: «Are you sure you want to continue connecting?» — введите yes и нажмите Enter.")
    pdf.h2("Шаг 4. Введите пароль")
    pdf.p("Введите пароль: rFbUTevAX_z9@j")
    pdf.p("При вводе пароль на экране не отображается — это нормально. Просто наберите его и нажмите Enter.")
    pdf.p("После успешного входа вы увидите приглашение командной строки, например: root@server:~#")

    # 4. Подключение с Windows
    pdf.add_page()
    pdf.h1("4. Подключение к серверу (Windows)")
    pdf.h2("Вариант A — Windows 10/11 (встроенный SSH)")
    pdf.p("1. Нажмите Win + R, введите cmd и нажмите Enter.")
    pdf.p("2. Выполните команду:")
    pdf.code_block("ssh root@45.91.237.133")
    pdf.p("3. Введите пароль при запросе.")
    pdf.h2("Вариант B — программа PuTTY")
    pdf.bullet("Скачайте PuTTY с официального сайта: https://www.putty.org/")
    pdf.bullet("Host Name: 45.91.237.133")
    pdf.bullet("Port: 22")
    pdf.bullet("Connection type: SSH")
    pdf.bullet("Нажмите Open, логин: root, пароль: rFbUTevAX_z9@j")

    # 5. Переход в папку проекта
    pdf.h1("5. Переход в папку проекта")
    pdf.p("После входа на сервер перейдите в каталог, где установлен бот:")
    pdf.code_block("cd /opt/lu_bot")
    pdf.p("Проверить, что вы в нужной папке, можно командой:")
    pdf.code_block("pwd")
    pdf.p("Должно отобразиться: /opt/lu_bot")

    # 6. Открытие .env
    pdf.h1("6. Открытие файла .env")
    pdf.p(
        "Файл .env — это текстовый файл с настройками. Его нужно редактировать из папки проекта "
        "командой nano (встроенный текстовый редактор в Linux)."
    )
    pdf.p("Находясь в /opt/lu_bot, выполните:")
    pdf.code_block("nano .env")
    pdf.p("Откроется редактор с содержимым файла. Каждая строка — одна настройка в формате:")
    pdf.code_block("ИМЯ_ПАРАМЕТРА=значение")
    pdf.p("Пример:")
    pdf.code_block("BOT_TOKEN=7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

    # 7. Редактирование в nano
    pdf.add_page()
    pdf.h1("7. Как редактировать файл в nano")
    pdf.table_row("Действие", "Клавиши / команда", header=True)
    pdf.table_row("Перемещение курсора", "Стрелки ← ↑ → ↓")
    pdf.table_row("Удалить символ", "Backspace или Delete")
    pdf.table_row("Вставить текст", "Правая кнопка мыши (в PuTTY) или Cmd+V (Mac Terminal)")
    pdf.table_row("Сохранить файл", "Ctrl + O, затем Enter")
    pdf.table_row("Выйти из редактора", "Ctrl + X")
    pdf.table_row("Отменить последнее действие", "Alt + U")
    pdf.ln(3)
    pdf.h2("Типичный сценарий изменения ключа")
    pdf.bullet("Откройте файл: nano .env")
    pdf.bullet("Найдите нужную строку (например BOT_TOKEN=...)")
    pdf.bullet("Удалите старое значение после знака = и вставьте новое")
    pdf.bullet("Сохраните: Ctrl+O → Enter")
    pdf.bullet("Выйдите: Ctrl+X")
    pdf.bullet("Перезапустите сервисы (см. раздел 10)")
    pdf.warning(
        "Не удаляйте названия параметров (часть до знака =). Меняйте только значение справа. "
        "Не добавляйте пробелы вокруг знака =."
    )

    # 8. Описание параметров
    pdf.h1("8. Описание параметров в .env")
    pdf.p("Ниже — основные группы настроек. Меняйте только те параметры, которые требуют обновления.")

    pdf.h2("8.1. Основные настройки бота")
    pdf.table_row("Параметр", "Описание", header=True)
    pdf.table_row("BOT_TOKEN", "Токен Telegram-бота от @BotFather")
    pdf.table_row("BOT_USERNAME", "Имя бота без @, например lumo_bot")
    pdf.table_row("ADMIN_IDS", "Telegram ID администраторов через запятую")
    pdf.table_row("WEBAPP_URL", "URL админ-панели (Mini App)")
    pdf.table_row("DATABASE_URL", "Строка подключения к PostgreSQL (обычно не менять)")
    pdf.table_row("REDIS_URL", "Строка подключения к Redis (обычно не менять)")
    pdf.ln(2)

    pdf.h2("8.2. Ссылки и мониторинг")
    pdf.table_row("Параметр", "Описание", header=True)
    pdf.table_row("RULES_LINK_1", "Ссылка на правила сервиса")
    pdf.table_row("RULES_LINK_2", "Ссылка на политику конфиденциальности")
    pdf.table_row("SENTRY_DSN", "DSN для Sentry (отслеживание ошибок), можно оставить пустым")
    pdf.table_row("OPENAI_API_KEY", "Ключ OpenAI для AI-функций LUMO")
    pdf.ln(2)

    pdf.h2("8.3. Webhook (опционально)")
    pdf.table_row("Параметр", "Описание", header=True)
    pdf.table_row("WEBHOOK_URL", "URL webhook для Telegram (если используется)")
    pdf.table_row("WEBHOOK_SECRET", "Секрет webhook")
    pdf.ln(2)

    pdf.add_page()
    pdf.h2("8.4. Платежи (ЮKassa / Telegram Stars)")
    pdf.table_row("Параметр", "Описание", header=True)
    pdf.table_row("PAYMENT_PROVIDER", "yookassa или stars")
    pdf.table_row("YOOKASSA_SHOP_ID", "Идентификатор магазина ЮKassa")
    pdf.table_row("YOOKASSA_SHOP_SECRET_ID", "Секретный ключ ЮKassa")
    pdf.table_row("YOOKASSA_RETURN_URL", "URL возврата после оплаты, напр. https://t.me/lumo_bot")
    pdf.table_row("SPARK_PRICE_RUB", "Цена 1 Искры в рублях")
    pdf.table_row("SPARK_PRICE_STARS", "Цена 1 Искры в Telegram Stars")
    pdf.ln(2)

    pdf.h2("8.5. Fragment — автовыплата Stars")
    pdf.p("Заполняется, если настроены автоматические выплаты через Fragment:")
    pdf.table_row("Параметр", "Описание", header=True)
    pdf.table_row("FRAGMENT_TON_SEED", "Seed-фраза TON-кошелька")
    pdf.table_row("FRAGMENT_TONAPI_KEY", "API-ключ TonAPI")
    pdf.table_row("FRAGMENT_STEL_SSID / TOKEN", "Cookies/токены Fragment")
    pdf.table_row("FRAGMENT_STEL_TON_TOKEN", "TON-токен Fragment")
    pdf.table_row("FRAGMENT_MIN_STARS", "Минимальная сумма вывода в Stars")
    pdf.ln(2)

    pdf.h2("8.6. Геопоиск (Yandex Geocoder)")
    pdf.table_row("Параметр", "Описание", header=True)
    pdf.table_row("YANDEX_GEOCODER_API_KEY", "Ключ Yandex Geocoder API")
    pdf.table_row("GEO_NEARBY_RADIUS_KM", "Радиус поиска «рядом», км (по умолчанию 300)")
    pdf.table_row("GEO_SAME_CITY_KM", "Радиус «тот же город», км (по умолчанию 25)")
    pdf.ln(2)
    pdf.p("Если параметр не используется — оставьте значение пустым (PARAM=).")

    # 9. Пример смены токена
    pdf.h1("9. Пример: замена токена бота")
    pdf.p("Допустим, @BotFather выдал новый токен. Действия:")
    pdf.code_block(
        """cd /opt/lu_bot
nano .env"""
    )
    pdf.p("Найдите строку BOT_TOKEN= и замените значение на новый токен.")
    pdf.p("Сохраните (Ctrl+O, Enter) и выйдите (Ctrl+X).")
    pdf.p("Перезапустите сервисы:")
    pdf.code_block("systemctl restart luma-bot luma-api luma-worker")
    pdf.p("Проверьте статус:")
    pdf.code_block("systemctl status luma-bot")

    # 10. Перезапуск после изменений .env
    pdf.add_page()
    pdf.h1("10. Перезапуск сервисов после изменения .env")
    pdf.p("После любого изменения .env нужно перезапустить три сервиса:")
    pdf.code_block("systemctl restart luma-bot luma-api luma-worker")
    pdf.p("Проверка, что всё работает:")
    pdf.code_block(
        """systemctl status luma-bot
systemctl status luma-api
systemctl status luma-worker"""
    )
    pdf.p("В строке Active должно быть: active (running).")
    pdf.p("Если статус failed — посмотрите логи:")
    pdf.code_block(
        """journalctl -u luma-bot -n 50 --no-pager
journalctl -u luma-api -n 50 --no-pager"""
    )

    # 11. Шпаргалка
    pdf.add_page()
    pdf.h1("11. Шпаргалка — все команды одним списком")
    pdf.h2("Вход на сервер")
    pdf.code_block("ssh root@45.91.237.133")
    pdf.h2("Редактирование .env")
    pdf.code_block(
        """cd /opt/lu_bot
nano .env"""
    )
    pdf.h2("Перезапуск после изменения .env")
    pdf.code_block("systemctl restart luma-bot luma-api luma-worker")
    pdf.h2("Проверка статуса")
    pdf.code_block(
        """systemctl status luma-bot
systemctl status luma-api
systemctl status luma-worker"""
    )
    pdf.ln(8)
    pdf.set_font("Main", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(
        0,
        5,
        "При возникновении проблем сохраните текст ошибки из терминала или сделайте скриншот — "
        "это поможет быстрее найти решение.",
        align="C",
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUTPUT))
    print(f"PDF создан: {OUTPUT}")


if __name__ == "__main__":
    build()
