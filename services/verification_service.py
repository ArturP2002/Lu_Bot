"""AI-проверка верификационного видео: живость, жест, произнесённый код."""

from __future__ import annotations

import base64
import json
import logging
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import cv2
from aiogram import Bot
from openai import AsyncOpenAI

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

GESTURE_HINTS = {
    "✌️": "peace / V-sign (указательный и средний палец вверх)",
    "👍": "thumbs up (большой палец вверх)",
    "🤟": "I love you / ILY (большой, указательный и мизинец)",
}

DIGIT_WORDS = {
    "ноль": "0",
    "нуль": "0",
    "один": "1",
    "раз": "1",
    "два": "2",
    "три": "3",
    "четыре": "4",
    "пять": "5",
    "шесть": "6",
    "семь": "7",
    "восемь": "8",
    "девять": "9",
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}


@dataclass
class VerificationCheckResult:
    """Результат AI-проверки верификации."""

    passed: bool
    liveness_ok: bool
    gesture_ok: bool
    code_ok: bool
    transcript: str
    reason: str


async def download_telegram_file(bot: Bot, file_id: str, destination: Path) -> Path:
    """Скачать файл Telegram во временный путь."""
    await bot.download(file_id, destination=destination)
    if not destination.exists() or destination.stat().st_size == 0:
        raise ValueError("Не удалось скачать файл Telegram")
    return destination


def extract_video_frames(video_path: Path, max_frames: int = 4) -> list[bytes]:
    """Извлечь несколько JPEG-кадров из видео равномерно по длительности."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError("Не удалось открыть видео для проверки")

    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total <= 0:
            # Fallback: читаем подряд до max_frames
            frames: list[bytes] = []
            while len(frames) < max_frames:
                ok, frame = cap.read()
                if not ok:
                    break
                frames.append(_encode_jpeg(frame))
            if not frames:
                raise ValueError("В видео не найдено кадров")
            return frames

        indices = sorted(
            {
                0,
                total - 1,
                *[min(total - 1, max(0, int(total * i / (max_frames + 1)))) for i in range(1, max_frames + 1)],
            }
        )[:max_frames]

        frames = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if ok and frame is not None:
                frames.append(_encode_jpeg(frame))
        if not frames:
            raise ValueError("Не удалось извлечь кадры из видео")
        return frames
    finally:
        cap.release()


def _encode_jpeg(frame) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise ValueError("Не удалось закодировать кадр")
    return buf.tobytes()


def _guess_image_mime(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _to_data_url(image_bytes: bytes, mime: str | None = None) -> str:
    return f"data:{mime or _guess_image_mime(image_bytes)};base64,{base64.b64encode(image_bytes).decode('ascii')}"


def normalize_spoken_digits(text: str) -> str:
    """Преобразовать речь в последовательность цифр."""
    lower = text.lower().replace("ё", "е")
    # Заменяем словесные цифры на символы
    for word, digit in sorted(DIGIT_WORDS.items(), key=lambda x: -len(x[0])):
        lower = re.sub(rf"\b{re.escape(word)}\b", digit, lower)
    return re.sub(r"\D", "", lower)


def code_mentioned(transcript: str, expected_code: str) -> bool:
    """Проверить, что ожидаемый код звучит в транскрипте."""
    digits = normalize_spoken_digits(transcript)
    if expected_code in digits:
        return True
    # Допуск: код произнесён с паузами / лишними звуками между цифрами
    pattern = r".*?".join(re.escape(d) for d in expected_code)
    return bool(re.search(pattern, digits))


async def transcribe_video(client: AsyncOpenAI, video_path: Path) -> str:
    """Распознать речь из видео через Whisper."""
    with video_path.open("rb") as f:
        result = await client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="ru",
        )
    return (result.text or "").strip()


async def analyze_liveness_and_gesture(
    client: AsyncOpenAI,
    *,
    frames: list[bytes],
    expected_gesture: str,
    expected_code: str,
    transcript: str,
) -> tuple[bool, bool, str]:
    """Проверить, что в кружке живой человек, и что показан нужный жест."""
    gesture_hint = GESTURE_HINTS.get(expected_gesture, expected_gesture)
    content: list[dict] = [
        {
            "type": "text",
            "text": (
                "Ты проверяешь верификацию пользователя dating-бота.\n"
                "Изображения — кадры из видеосообщения (кружок). Сравнивать с фото анкеты НЕ нужно: "
                "фото анкеты можно менять, личность по фото не подтверждаем.\n\n"
                f"Ожидаемый жест: {expected_gesture} ({gesture_hint}).\n"
                f"Ожидаемый код (должен быть произнесён): {expected_code}.\n"
                f"Транскрипт речи из видео: «{transcript or 'пусто'}».\n\n"
                "Оцени два независимых критерия:\n\n"
                "1) liveness_ok — проверка, что это живой человек:\n"
                "   - true, если на кадрах видно живое человеческое лицо (можно не крупным планом).\n"
                "   - Допускаются: другой ракурс, лицо далеко/частично, мимика, освещение, "
                "очки, макияж, качество камеры.\n"
                "   - false, если это маска, чужое фото/распечатка, фото или видео на экране телефона, "
                "манекен, или лица совсем не видно.\n"
                "   - Не сравнивай внешность ни с каким другим фото. Нам важно только, что человек живой.\n"
                "   - При сомнении, но лицо живого человека видно — ставь true.\n\n"
                "2) gesture_ok — ЖЁСТКАЯ проверка жеста:\n"
                "   - true только если на хотя бы одном кадре чётко виден именно ожидаемый жест рукой.\n"
                "   - Похожий, но другой жест, размытый/неразборчивый жест, отсутствие руки → false.\n"
                "   - При сомнении ставь false.\n\n"
                "Ответь строго JSON без markdown:\n"
                '{"liveness_ok": true/false, "gesture_ok": true/false, "reason": "кратко по-русски"}'
            ),
        },
    ]
    for frame in frames:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": _to_data_url(frame), "detail": "high"},
            }
        )

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты модератор liveness-проверки. Не сравнивай лицо с фото анкеты. "
                    "Нужно убедиться, что в кружке живой человек, а не фото/экран/маска. "
                    "К жесту относись строго. Отвечай только JSON."
                ),
            },
            {"role": "user", "content": content},
        ],
        response_format={"type": "json_object"},
        max_tokens=300,
        temperature=0,
    )
    raw = response.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Невалидный JSON от Vision: %s", raw)
        return False, False, "Не удалось разобрать ответ проверки"

    liveness_ok = bool(data.get("liveness_ok"))
    gesture_ok = bool(data.get("gesture_ok"))
    reason = str(data.get("reason") or "").strip() or "Проверка завершена"
    return liveness_ok, gesture_ok, reason


async def verify_video_note(
    bot: Bot,
    *,
    video_file_id: str,
    expected_code: str,
    expected_gesture: str,
) -> VerificationCheckResult:
    """AI-проверка кружка: живой человек, жест, произнесённый код."""
    if not settings.openai_api_key:
        return VerificationCheckResult(
            passed=False,
            liveness_ok=False,
            gesture_ok=False,
            code_ok=False,
            transcript="",
            reason="AI-проверка временно недоступна. Попробуй позже.",
        )

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    with tempfile.TemporaryDirectory(prefix="luma_verify_") as tmp:
        tmp_path = Path(tmp)
        video_path = tmp_path / "video.mp4"

        await download_telegram_file(bot, video_file_id, video_path)
        frames = extract_video_frames(video_path)

        try:
            transcript = await transcribe_video(client, video_path)
        except Exception:
            logger.exception("Whisper transcription failed")
            transcript = ""

        code_ok = code_mentioned(transcript, expected_code) if transcript else False

        try:
            liveness_ok, gesture_ok, reason = await analyze_liveness_and_gesture(
                client,
                frames=frames,
                expected_gesture=expected_gesture,
                expected_code=expected_code,
                transcript=transcript,
            )
        except Exception:
            logger.exception("Vision analysis failed")
            return VerificationCheckResult(
                passed=False,
                liveness_ok=False,
                gesture_ok=False,
                code_ok=code_ok,
                transcript=transcript,
                reason="Ошибка AI-проверки. Попробуй записать кружок ещё раз.",
            )

        if not transcript:
            reason = f"{reason} Не удалось распознать речь — произнеси код громче и чётче."

        passed = liveness_ok and gesture_ok and code_ok
        if passed:
            reason = "Живой человек, жест верный, код произнесён."
        else:
            parts = []
            if not liveness_ok:
                parts.append("не видно живого человека")
            if not gesture_ok:
                parts.append("жест не распознан или неверный")
            if not code_ok:
                parts.append(f"код {expected_code} не услышан")
            reason = "Не пройдено: " + "; ".join(parts) + f". {reason}"

        return VerificationCheckResult(
            passed=passed,
            liveness_ok=liveness_ok,
            gesture_ok=gesture_ok,
            code_ok=code_ok,
            transcript=transcript,
            reason=reason,
        )
