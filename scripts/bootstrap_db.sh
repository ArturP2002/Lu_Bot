#!/usr/bin/env bash
# Полная инициализация пустой БД: таблицы + версия Alembic + seed.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON="${ROOT_DIR}/.venv/bin/python"
ALEMBIC="${ROOT_DIR}/.venv/bin/alembic"

if [[ ! -x "$PYTHON" ]]; then
  echo "Не найден .venv: $PYTHON"
  exit 1
fi

echo "==> Создание таблиц (init_db)"
PYTHONPATH="$ROOT_DIR" "$PYTHON" "$ROOT_DIR/scripts/init_db.py"

echo "==> Синхронизация версии Alembic"
"$ALEMBIC" stamp head

echo "==> Начальные данные (seed)"
PYTHONPATH="$ROOT_DIR" "$PYTHON" "$ROOT_DIR/scripts/seed.py"

echo
echo "БД готова."
