"""Медиа анкеты: несколько фото + видео для Premium."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Literal

from aiogram import Bot
from aiogram.types import Message
from redis.asyncio import Redis

from models import User
from services.user_service import is_premium

logger = logging.getLogger(__name__)

MAX_PROFILE_MEDIA = 10
ALBUM_WAIT_SEC = 1.0
MediaKind = Literal["photo", "video"]


@dataclass(frozen=True)
class ProfileMedia:
    kind: MediaKind
    file_id: str
    message_id: int | None = None


def get_profile_media(user: User) -> list[ProfileMedia]:
    """Список медиа анкеты. Fallback на одиночное photo_file_id."""
    items: list[ProfileMedia] = []
    raw = getattr(user, "media_json", None)
    if raw:
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            data = []
        if isinstance(data, list):
            for row in data:
                if not isinstance(row, dict):
                    continue
                kind = row.get("type") or row.get("kind")
                fid = row.get("file_id")
                if kind in ("photo", "video") and fid:
                    items.append(ProfileMedia(kind=kind, file_id=str(fid)))
    if not items:
        fid = getattr(user, "photo_file_id", None)
        if fid:
            items.append(ProfileMedia(kind="photo", file_id=fid))
    return items[:MAX_PROFILE_MEDIA]


def set_profile_media(user: User, items: list[ProfileMedia]) -> None:
    """Сохранить альбом и синхронизировать photo_file_id (первое фото)."""
    items = items[:MAX_PROFILE_MEDIA]
    user.media_json = json.dumps(
        [{"type": i.kind, "file_id": i.file_id} for i in items],
        ensure_ascii=False,
    )
    first_photo = next((i for i in items if i.kind == "photo"), None)
    user.photo_file_id = first_photo.file_id if first_photo else None


def merge_profile_media(
    existing: list[ProfileMedia],
    incoming: list[ProfileMedia],
    *,
    limit: int = MAX_PROFILE_MEDIA,
) -> tuple[list[ProfileMedia], int]:
    """Добавить новые файлы к уже сохранённым. Возвращает (итог, сколько не влезло)."""
    seen = {item.file_id for item in existing}
    merged = [
        ProfileMedia(kind=item.kind, file_id=item.file_id) for item in existing[:limit]
    ]
    dropped = 0
    for item in incoming:
        if item.file_id in seen:
            continue
        if len(merged) >= limit:
            dropped += 1
            continue
        merged.append(ProfileMedia(kind=item.kind, file_id=item.file_id))
        seen.add(item.file_id)
    return merged, dropped


def media_from_message(message: Message) -> ProfileMedia | None:
    if message.photo:
        return ProfileMedia(kind="photo", file_id=message.photo[-1].file_id, message_id=message.message_id)
    if message.video:
        return ProfileMedia(kind="video", file_id=message.video.file_id, message_id=message.message_id)
    if message.video_note:
        return ProfileMedia(kind="video", file_id=message.video_note.file_id, message_id=message.message_id)
    return None


async def collect_album(message: Message, redis: Redis) -> list[ProfileMedia] | None:
    """Собрать альбом Telegram. None — это не лидер, обработчик должен выйти."""
    item = media_from_message(message)
    if item is None:
        return None
    group_id = message.media_group_id
    if not group_id:
        return [item]

    key = f"album:{message.chat.id}:{group_id}"
    lock_key = f"{key}:leader"
    payload = json.dumps(
        {"type": item.kind, "file_id": item.file_id, "mid": item.message_id},
        ensure_ascii=False,
    )
    await redis.rpush(key, payload)
    await redis.expire(key, 30)
    is_leader = await redis.set(lock_key, "1", nx=True, ex=30)
    if not is_leader:
        return None

    await asyncio.sleep(ALBUM_WAIT_SEC)
    raw = await redis.lrange(key, 0, -1)
    await redis.delete(key, lock_key)

    items: list[ProfileMedia] = []
    seen: set[str] = set()
    for row in raw:
        text = row.decode() if isinstance(row, (bytes, bytearray)) else str(row)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        kind = data.get("type")
        fid = data.get("file_id")
        if kind not in ("photo", "video") or not fid or fid in seen:
            continue
        seen.add(fid)
        mid = data.get("mid")
        items.append(
            ProfileMedia(
                kind=kind,
                file_id=str(fid),
                message_id=int(mid) if mid is not None else None,
            )
        )
    return items[:MAX_PROFILE_MEDIA]


async def ingest_profile_media(
    bot: Bot,
    user: User,
    items: list[ProfileMedia],
) -> tuple[list[ProfileMedia], str | None, str | None]:
    """Отфильтровать, промодерировать и вернуть (accepted, error_key, warning_key)."""
    from services.luma_ai_service import moderate_telegram_photo, moderate_telegram_video

    allow_video = is_premium(user)
    dropped_video = False
    filtered: list[ProfileMedia] = []
    for item in items:
        if item.kind == "video" and not allow_video:
            dropped_video = True
            continue
        filtered.append(item)
    filtered = filtered[:MAX_PROFILE_MEDIA]

    if not filtered:
        if dropped_video:
            return [], "MEDIA_VIDEO_PREMIUM", None
        return [], "MEDIA_NEED_FILE", None

    async def _check(item: ProfileMedia) -> tuple[ProfileMedia, bool, str]:
        try:
            if item.kind == "video":
                ok, reason = await moderate_telegram_video(bot, item.file_id)
            else:
                ok, reason = await moderate_telegram_photo(bot, item.file_id)
            return item, ok, reason
        except Exception as exc:
            logger.warning("profile media moderation failed: %s", exc)
            return item, True, ""

    results = await asyncio.gather(*[_check(i) for i in filtered], return_exceptions=True)
    accepted: list[ProfileMedia] = []
    first_reason = ""
    for result in results:
        if isinstance(result, Exception):
            logger.warning("profile media moderation failed: %s", result)
            continue
        item, ok, reason = result
        if ok:
            accepted.append(item)
        elif not first_reason:
            first_reason = reason or "нарушение"

    if not accepted:
        return [], "MODERATION_BLOCKED", first_reason or "нарушение"

    warning = "MEDIA_VIDEO_DROPPED" if dropped_video else None
    return accepted, None, warning


async def consume_profile_media_message(
    message: Message,
    user: User,
    redis: Redis,
) -> tuple[list[ProfileMedia] | None, str | None, str | None]:
    """Собрать альбом, промодерировать, удалить исходные сообщения пользователя.

    (None, None, None) — это не лидер альбома, хендлер должен выйти.
    """
    from bot.utils.messaging import safe_delete

    items = await collect_album(message, redis)
    if items is None:
        return None, None, None
    accepted, err_key, warning = await ingest_profile_media(message.bot, user, items)
    for item in items:
        if item.message_id:
            await safe_delete(bot=message.bot, chat_id=message.chat.id, message_id=item.message_id)
    return accepted, err_key, warning
