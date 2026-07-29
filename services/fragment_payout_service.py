"""Выплата Искр через Fragment (покупка Telegram Stars на @username)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class FragmentPayoutResult:
    ok: bool
    stars_sent: int = 0
    transaction_id: str | None = None
    recipient_username: str | None = None
    error: str | None = None


def normalize_username(username: str) -> str:
    """Нормализовать Telegram username для Fragment."""
    clean = username.strip().lstrip("@")
    if not clean or not clean.replace("_", "").isalnum():
        raise ValueError("Некорректный username")
    return f"@{clean}"


def _fragment_cookies() -> dict[str, str]:
    settings = get_settings()
    return {
        "stel_ssid": settings.fragment_stel_ssid.strip(),
        "stel_dt": settings.fragment_stel_dt.strip() or "-180",
        "stel_token": settings.fragment_stel_token.strip(),
        "stel_ton_token": settings.fragment_stel_ton_token.strip(),
    }


async def payout_stars_via_fragment(
    username: str | None,
    stars_amount: int,
    *,
    note: str = "LUMA payout",
) -> FragmentPayoutResult:
    """
    Реальная выплата Stars пользователю через Fragment.
    1 Искра (net) = 1 Star.
    """
    _ = note  # зарезервировано под memo/логирование
    settings = get_settings()

    if not username:
        return FragmentPayoutResult(ok=False, error="У пользователя нет @username в Telegram")

    if not settings.fragment_configured:
        return FragmentPayoutResult(ok=False, error="Fragment не настроен на сервере")

    if stars_amount <= 0:
        return FragmentPayoutResult(ok=False, error="Сумма должна быть > 0")

    if stars_amount < settings.fragment_min_stars:
        return FragmentPayoutResult(
            ok=False,
            error=f"Минимальная выплата через Fragment — {settings.fragment_min_stars} Stars",
        )

    try:
        recipient = normalize_username(username)
    except ValueError as e:
        return FragmentPayoutResult(ok=False, error=str(e))

    try:
        from pyfragment import FragmentClient

        async with FragmentClient(
            seed=settings.fragment_ton_seed.strip(),
            api_key=settings.fragment_tonapi_key.strip(),
            cookies=_fragment_cookies(),
            wallet_version=settings.fragment_wallet_version.strip() or "V5R1",
        ) as client:
            result = await client.purchase_stars(
                recipient,
                stars_amount,
                show_sender=settings.fragment_show_sender,
            )
            tx_id = getattr(result, "transaction_id", None)
            amount = int(getattr(result, "amount", stars_amount) or stars_amount)
            uname = getattr(result, "username", recipient)
            return FragmentPayoutResult(
                ok=True,
                stars_sent=amount,
                transaction_id=str(tx_id) if tx_id else None,
                recipient_username=str(uname) if uname else recipient,
            )
    except Exception as e:
        logger.exception("Fragment payout failed for %s amount=%s", recipient, stars_amount)
        return FragmentPayoutResult(ok=False, error=str(e))
