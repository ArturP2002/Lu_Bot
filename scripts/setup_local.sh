#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DB_USER="${LUMA_DB_USER:-luma}"
DB_PASS="${LUMA_DB_PASS:-luma}"
DB_NAME="${LUMA_DB_NAME:-luma}"
DB_HOST="${LUMA_DB_HOST:-localhost}"
DB_PORT="${LUMA_DB_PORT:-5432}"
PG_SUPERUSER="${PG_SUPERUSER:-$(whoami)}"

echo "==> Проверка Redis"
if ! redis-cli ping >/dev/null 2>&1; then
  echo "Redis не отвечает. Запустите: brew services start redis"
  exit 1
fi
echo "Redis OK"

echo "==> Проверка PostgreSQL"
if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" >/dev/null 2>&1; then
  echo "PostgreSQL не отвечает. Запустите: brew services start postgresql@16"
  exit 1
fi
echo "PostgreSQL OK"

echo "==> Создание роли и базы данных ($DB_NAME)"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$PG_SUPERUSER" -d postgres -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$DB_USER') THEN
    CREATE ROLE $DB_USER WITH LOGIN PASSWORD '$DB_PASS';
  END IF;
END
\$\$;
ALTER ROLE $DB_USER WITH LOGIN PASSWORD '$DB_PASS';
SELECT 'CREATE DATABASE $DB_NAME OWNER $DB_USER'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\\gexec
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
SQL

echo "==> Создание таблиц"
PYTHONPATH="$ROOT_DIR" "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/init_db.py"

echo
echo "Локальное окружение готово."
echo "Запуск бота: $ROOT_DIR/.venv/bin/python $ROOT_DIR/main.py"
