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
alembic upgrade head
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
