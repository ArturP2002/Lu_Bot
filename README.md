# LUMA Telegram Bot

Telegram-бот знакомств и мероприятий LUMA.

## Стек

- aiogram 3
- FastAPI
- PostgreSQL + SQLAlchemy async
- Redis (FSM, rate limit, очереди)
- ARQ (фоновые задачи)
- Admin Mini App (React + Vite)

## Быстрый старт

```bash
cp .env.example .env
# Заполните BOT_TOKEN и ADMIN_IDS

docker compose up -d postgres redis
pip install -r requirements.txt
./scripts/bootstrap_db.sh
python main.py
```

API: `python run_api.py`  
Worker: `arq tasks.worker.WorkerSettings`

## Структура

- `bot/` — Telegram-бот (handlers, keyboards, texts)
- `api/` — REST API для Admin Mini App
- `services/` — бизнес-логика
- `models/` — модели БД
- `admin-miniapp/` — админ-панель (Mini App)

Все тексты бота и комментарии в коде — на русском языке.

## Партнерка и лидерборд

После обновления примените миграции: `alembic upgrade head`.
Миграция 007 пересчитывает рефералов с учетом верификации; ранее выданные награды сохраняются.

В лидерборде участвуют заполненные незаблокированные анкеты. Счет — количество
приглашённых с заполненной анкетой и успешной верификацией плюс ручной бонус из
админки. При равном счете выше пользователь с меньшим ID. Ручной бонус влияет
только на лидерборд, а награды рассчитываются по реальным подтверждённым рефералам.
Админ задает бонус по Telegram ID в разделе «Партнерка · Лидерборд»; ноль убирает бонус.

Тесты: `pip install -r requirements-dev.txt`, затем `python -m pytest tests`.
Админка: `cd admin-miniapp`, `npm ci`, `npm run build`.
