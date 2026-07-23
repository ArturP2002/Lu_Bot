"""Инициализация базы данных."""

import asyncio
import sys
from pathlib import Path

# Запуск как `python scripts/init_db.py` — добавляем корень проекта в PYTHONPATH
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from core.database import Base, get_engine
import models  # noqa: F401


async def init_db() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Мягкие миграции для уже существующих БД
        await conn.execute(
            text(
                "ALTER TABLE withdraw_requests "
                "ADD COLUMN IF NOT EXISTS requisites TEXT"
            )
        )
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS language VARCHAR(8) DEFAULT 'ru'")
        )
        await conn.execute(
            text(
                "ALTER TABLE withdraw_requests "
                "ADD COLUMN IF NOT EXISTS method VARCHAR(16) DEFAULT 'requisites'"
            )
        )
        await conn.execute(
            text("ALTER TABLE withdraw_requests ADD COLUMN IF NOT EXISTS payout_meta TEXT")
        )
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS profile_skips (
                    id SERIAL PRIMARY KEY,
                    from_user_id INTEGER NOT NULL REFERENCES users(id),
                    to_user_id INTEGER NOT NULL REFERENCES users(id),
                    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
                    CONSTRAINT uq_profile_skip_pair UNIQUE (from_user_id, to_user_id)
                )
                """
            )
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_profile_skips_from_user_id ON profile_skips (from_user_id)")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_profile_skips_to_user_id ON profile_skips (to_user_id)")
        )
    print("Таблицы созданы.")


if __name__ == "__main__":
    asyncio.run(init_db())
