#!/usr/bin/env bash
# Поднимает Postgres/Redis и проверяет, что бот сможет к ним подключиться.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a
  # shellcheck disable=SC1090
  source .env
  set +a
fi

REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

echo "==> docker compose up -d postgres redis"
docker compose up -d postgres redis

echo "==> ожидание healthcheck"
for _ in $(seq 1 30); do
  pg_ok=0
  redis_ok=0
  docker compose exec -T postgres pg_isready -U luma -d luma >/dev/null 2>&1 && pg_ok=1
  docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG && redis_ok=1
  if [[ "$pg_ok" -eq 1 && "$redis_ok" -eq 1 ]]; then
    break
  fi
  sleep 1
done

echo "==> postgres"
docker compose exec -T postgres pg_isready -U luma -d luma

echo "==> redis (внутри контейнера)"
docker compose exec -T redis redis-cli ping

echo "==> redis с хоста (как в REDIS_URL)"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  REDIS_URL="$REDIS_URL" "$ROOT/.venv/bin/python" - <<'PY'
import os, sys
import redis
url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
try:
    print(redis.Redis.from_url(url, socket_connect_timeout=3).ping())
except Exception as e:
    print(f"FAIL: {e}", file=sys.stderr)
    sys.exit(1)
PY
elif command -v redis-cli >/dev/null 2>&1; then
  redis-cli ping
else
  echo "skip: нет .venv и redis-cli"
fi

echo "==> кто слушает 5432/6379"
ss -lntp 2>/dev/null | grep -E ':5432|:6379' || netstat -lntp 2>/dev/null | grep -E ':5432|:6379' || true

echo "OK: infra готова"
