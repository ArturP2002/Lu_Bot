#!/usr/bin/env python3
"""Одноразовый backfill координат по городам.

Пример:
  .venv/bin/python scripts/backfill_geo.py
  .venv/bin/python scripts/backfill_geo.py --limit 50
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill user/event coordinates via Yandex Geocoder")
    parser.add_argument("--limit", type=int, default=None, help="Макс. число уникальных городов")
    parser.add_argument("--delay", type=float, default=0.35, help="Пауза между запросами к API")
    args = parser.parse_args()

    from services.geo_backfill import backfill_user_event_geo

    stats = await backfill_user_event_geo(delay_sec=args.delay, limit_cities=args.limit)
    print(stats)


if __name__ == "__main__":
    asyncio.run(main())
