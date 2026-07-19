"""FastAPI приложение LUMA."""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from core.database import get_session
from models import Broadcast, Complaint, Event, Payment, SparksTransaction, User, Verification, WithdrawRequest
from models.entities import BloggerProfile, Referral, ReferralReward
from services.sparks_service import add_transaction
from services.user_service import is_premium
from services.blogger_service import approve_blogger, reject_blogger
from services.app_settings_service import (
    SETTING_META,
    env_defaults,
    get_all_settings,
    upsert_setting,
)

logger = logging.getLogger(__name__)
settings = get_settings()
app = FastAPI(title="LUMA API", description="API для Admin Mini App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def validate_init_data(init_data: str) -> dict:
    """Валидация Telegram WebApp initData."""
    parsed = dict(x.split("=", 1) for x in init_data.split("&") if "=" in x)
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(401, "Нет hash")

    data_check = "\n".join(f"{k}={unquote(v)}" for k, v in sorted(parsed.items()))
    secret = hmac.new(b"WebAppData", settings.bot_token.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if computed != received_hash:
        raise HTTPException(401, "Неверная подпись")

    user_data = json.loads(unquote(parsed.get("user", "{}")))
    if user_data.get("id") not in settings.admin_id_list:
        raise HTTPException(403, "Нет доступа")
    return user_data


async def admin_auth(x_telegram_init_data: str = Header(...)) -> dict:
    return validate_init_data(x_telegram_init_data)


def _user_brief(u: User | None) -> dict | None:
    if not u:
        return None
    return {
        "id": u.id,
        "telegram_id": u.telegram_id,
        "display_name": u.display_name,
        "username": u.username,
        "city": u.city,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/admin/stats")
async def admin_stats(session: AsyncSession = Depends(get_session), _=Depends(admin_auth)):
    users = await session.scalar(select(func.count(User.id)))
    events = await session.scalar(
        select(func.count(Event.id)).where(Event.status != "deleted")
    )
    complaints = await session.scalar(
        select(func.count(Complaint.id)).where(Complaint.status == "pending")
    )
    verifications = await session.scalar(
        select(func.count(Verification.id)).where(Verification.status == "pending")
    )
    withdraws = await session.scalar(
        select(func.count(WithdrawRequest.id)).where(WithdrawRequest.status == "pending")
    )
    premium_users = await session.scalar(
        select(func.count(User.id)).where(User.premium_until.is_not(None))
    )
    payments_sum = await session.scalar(
        select(func.coalesce(func.sum(Payment.amount_sparks), 0)).where(Payment.status == "succeeded")
    )
    payments_rub = await session.scalar(
        select(func.coalesce(func.sum(Payment.amount_rub), 0.0)).where(Payment.status == "succeeded")
    )
    active_7d = await session.scalar(
        select(func.count(User.id)).where(
            User.updated_at >= datetime.now(timezone.utc) - timedelta(days=7)
        )
    )
    sparks_in = await session.scalar(
        select(func.coalesce(func.sum(SparksTransaction.amount), 0)).where(SparksTransaction.amount > 0)
    )
    sparks_out = await session.scalar(
        select(func.coalesce(func.sum(SparksTransaction.amount), 0)).where(SparksTransaction.amount < 0)
    )
    return {
        "users": users or 0,
        "events": events or 0,
        "pending_complaints": complaints or 0,
        "pending_verifications": verifications or 0,
        "pending_withdraws": withdraws or 0,
        "premium_users": premium_users or 0,
        "payments_sparks": int(payments_sum or 0),
        "payments_rub": float(payments_rub or 0),
        "active_users_7d": active_7d or 0,
        "sparks_in": int(sparks_in or 0),
        "sparks_out": abs(int(sparks_out or 0)),
        "revenue_estimate": float(payments_rub or 0),
    }


@app.get("/admin/users")
async def admin_users(
    q: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_auth),
):
    stmt = select(User).order_by(User.id.desc()).limit(100)
    if q and q.strip():
        term = f"%{q.strip()}%"
        filters = [User.display_name.ilike(term), User.username.ilike(term), User.city.ilike(term)]
        if q.strip().isdigit():
            filters.append(User.telegram_id == int(q.strip()))
            filters.append(User.id == int(q.strip()))
        stmt = select(User).where(or_(*filters)).order_by(User.id.desc()).limit(100)

    result = await session.execute(stmt)
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "telegram_id": u.telegram_id,
            "username": u.username,
            "display_name": u.display_name,
            "city": u.city,
            "age": u.age,
            "verified": u.verified,
            "premium": is_premium(u),
            "premium_until": str(u.premium_until) if u.premium_until else None,
            "disabled": u.disabled,
            "is_banned": u.is_banned,
            "warning_count": u.warning_count,
            "sparks_balance": u.sparks_balance,
            "created_at": str(u.created_at) if u.created_at else None,
        }
        for u in users
    ]


class UserUpdate(BaseModel):
    is_banned: bool | None = None
    sparks_delta: int | None = None
    premium_days: int | None = None


@app.get("/admin/users/{user_id}")
async def admin_user_detail(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_auth),
):
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(User).options(selectinload(User.goal)).where(User.id == user_id)
    )
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(404, "Пользователь не найден")

    txs = (
        await session.execute(
            select(SparksTransaction)
            .where(SparksTransaction.user_id == u.id)
            .order_by(SparksTransaction.id.desc())
            .limit(20)
        )
    ).scalars().all()
    payments = (
        await session.execute(
            select(Payment).where(Payment.user_id == u.id).order_by(Payment.id.desc()).limit(20)
        )
    ).scalars().all()

    goal = None
    if u.goal:
        goal = {
            "title": u.goal.title,
            "target_sparks": u.goal.target_sparks,
            "collected_sparks": u.goal.collected_sparks,
        }

    return {
        "id": u.id,
        "telegram_id": u.telegram_id,
        "username": u.username,
        "display_name": u.display_name,
        "country": u.country,
        "city": u.city,
        "age": u.age,
        "gender": u.gender,
        "seeking": u.seeking,
        "visible_to": u.visible_to,
        "bio": u.bio,
        "contact_phone": u.contact_phone,
        "photo_file_id": u.photo_file_id,
        "profile_completed": u.profile_completed,
        "sparks_balance": u.sparks_balance,
        "rating_avg": u.rating_avg,
        "rating_count": u.rating_count,
        "events_attended": u.events_attended,
        "events_organized": u.events_organized,
        "verified": u.verified,
        "premium": is_premium(u),
        "premium_until": str(u.premium_until) if u.premium_until else None,
        "disabled": u.disabled,
        "is_banned": u.is_banned,
        "warning_count": u.warning_count,
        "referral_code": u.referral_code,
        "referral_track": u.referral_track,
        "referral_count": u.referral_count,
        "goal": goal,
        "created_at": str(u.created_at) if u.created_at else None,
        "updated_at": str(u.updated_at) if u.updated_at else None,
        "recent_transactions": [
            {
                "id": t.id,
                "amount": t.amount,
                "tx_type": t.tx_type,
                "created_at": str(t.created_at) if t.created_at else None,
            }
            for t in txs
        ],
        "recent_payments": [
            {
                "id": p.id,
                "provider": p.provider,
                "amount_sparks": p.amount_sparks,
                "amount_rub": p.amount_rub,
                "status": p.status,
                "created_at": str(p.created_at) if p.created_at else None,
            }
            for p in payments
        ],
    }


@app.patch("/admin/users/{user_id}")
async def update_user(
    user_id: int,
    body: UserUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_auth),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    if body.is_banned is not None:
        user.is_banned = body.is_banned
    if body.sparks_delta is not None and body.sparks_delta != 0:
        await add_transaction(session, user.id, body.sparks_delta, "admin_adjust")
    if body.premium_days is not None:
        now = datetime.now(timezone.utc)
        if body.premium_days == 0:
            user.premium_until = None
        elif body.premium_days < 0:
            user.premium_until = datetime(2099, 12, 31, tzinfo=timezone.utc)
        else:
            base = user.premium_until if user.premium_until and user.premium_until > now else now
            if base.tzinfo is None:
                base = base.replace(tzinfo=timezone.utc)
            user.premium_until = base + timedelta(days=body.premium_days)
    return {
        "ok": True,
        "is_banned": user.is_banned,
        "sparks_balance": user.sparks_balance,
        "premium_until": str(user.premium_until) if user.premium_until else None,
    }


@app.get("/admin/complaints")
async def admin_complaints(session: AsyncSession = Depends(get_session), _=Depends(admin_auth)):
    result = await session.execute(
        select(Complaint).where(Complaint.status == "pending").order_by(Complaint.id.desc())
    )
    complaints = result.scalars().all()
    out = []
    for c in complaints:
        target = await session.get(User, c.target_user_id) if c.target_user_id else None
        reporter = await session.get(User, c.reporter_id) if c.reporter_id else None
        event = await session.get(Event, c.event_id) if c.event_id else None
        out.append(
            {
                "id": c.id,
                "type": c.complaint_type,
                "text": c.text,
                "target_user_id": c.target_user_id,
                "target_user": _user_brief(target),
                "reporter": _user_brief(reporter),
                "event_id": c.event_id,
                "event_title": event.title if event else None,
                "created_at": str(c.created_at) if c.created_at else None,
            }
        )
    return out


class ComplaintDecision(BaseModel):
    decision: str  # block, warning, reject


@app.patch("/admin/complaints/{complaint_id}")
async def resolve_complaint(
    complaint_id: int,
    body: ComplaintDecision,
    session: AsyncSession = Depends(get_session),
    admin=Depends(admin_auth),
):
    if body.decision not in ("block", "warning", "reject"):
        raise HTTPException(400, "Неверное решение")

    complaint = await session.get(Complaint, complaint_id)
    if not complaint:
        raise HTTPException(404, "Жалоба не найдена")

    complaint.status = "resolved" if body.decision != "reject" else "rejected"
    complaint.admin_decision = body.decision
    complaint.admin_id = admin["id"]
    complaint.resolved_at = datetime.now(timezone.utc)

    if body.decision == "block" and complaint.target_user_id:
        user = await session.get(User, complaint.target_user_id)
        if user:
            user.is_banned = True
    elif body.decision == "warning" and complaint.target_user_id:
        user = await session.get(User, complaint.target_user_id)
        if user:
            user.warning_count += 1

    return {"ok": True}


@app.get("/admin/verifications")
async def admin_verifications(session: AsyncSession = Depends(get_session), _=Depends(admin_auth)):
    result = await session.execute(
        select(Verification).where(Verification.status == "pending").order_by(Verification.id.desc())
    )
    out = []
    for v in result.scalars().all():
        user = await session.get(User, v.user_id)
        out.append(
            {
                "id": v.id,
                "user_id": v.user_id,
                "user": _user_brief(user),
                "code": v.code,
                "gesture": v.gesture,
                "video_file_id": v.video_file_id,
                "created_at": str(v.created_at) if v.created_at else None,
            }
        )
    return out


@app.patch("/admin/verifications/{verification_id}/approve")
async def approve_verification(
    verification_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_auth),
):
    v = await session.get(Verification, verification_id)
    if not v:
        raise HTTPException(404, "Заявка не найдена")
    if v.status != "pending":
        raise HTTPException(400, "Заявка уже обработана")
    v.status = "approved"
    user = await session.get(User, v.user_id)
    if user:
        user.verified = True
        from services.referral_service import process_referral_on_verification

        await process_referral_on_verification(session, user)
    return {"ok": True}


@app.patch("/admin/verifications/{verification_id}/reject")
async def reject_verification(
    verification_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_auth),
):
    v = await session.get(Verification, verification_id)
    if not v:
        raise HTTPException(404, "Заявка не найдена")
    if v.status != "pending":
        raise HTTPException(400, "Заявка уже обработана")
    v.status = "rejected"
    return {"ok": True}


@app.get("/admin/media/{file_id}")
async def admin_media(file_id: str, _=Depends(admin_auth)):
    """Прокси Telegram file по file_id для превью в админке."""
    from io import BytesIO

    from aiogram import Bot

    bot = Bot(token=settings.bot_token)
    try:
        file = await bot.get_file(file_id)
        if not file.file_path:
            raise HTTPException(404, "Файл не найден")
        buf = BytesIO()
        await bot.download_file(file.file_path, destination=buf)
        data = buf.getvalue()
        content_type = "application/octet-stream"
        lower = file.file_path.lower()
        if lower.endswith((".jpg", ".jpeg")):
            content_type = "image/jpeg"
        elif lower.endswith(".png"):
            content_type = "image/png"
        elif lower.endswith(".webp"):
            content_type = "image/webp"
        elif lower.endswith((".mp4", ".mov")):
            content_type = "video/mp4"
        elif lower.endswith(".webm"):
            content_type = "video/webm"
        return Response(content=data, media_type=content_type)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("media proxy error: %s", e)
        raise HTTPException(404, "Не удалось загрузить файл") from e
    finally:
        await bot.session.close()


class BroadcastFilters(BaseModel):
    gender: str | None = None  # all | male | female | other
    premium: str | None = None  # all | premium | free


class BroadcastCreate(BaseModel):
    message_text: str
    filters: BroadcastFilters | None = None
    filters_json: str | None = None
    target_user_ids: list[int] | None = None


@app.get("/admin/broadcasts")
async def list_broadcasts(session: AsyncSession = Depends(get_session), _=Depends(admin_auth)):
    result = await session.execute(select(Broadcast).order_by(Broadcast.id.desc()).limit(50))
    out = []
    for b in result.scalars().all():
        filters = None
        if b.filters_json:
            try:
                filters = json.loads(b.filters_json)
            except json.JSONDecodeError:
                filters = None
        out.append(
            {
                "id": b.id,
                "message_text": b.message_text,
                "status": b.status,
                "sent_count": b.sent_count,
                "total_count": b.total_count,
                "filters": filters,
                "created_at": str(b.created_at) if b.created_at else None,
            }
        )
    return out


async def _run_broadcast_job(broadcast_id: int) -> None:
    from core.database import get_session_factory
    from tasks.worker import send_broadcast

    try:
        await send_broadcast({}, broadcast_id)
    except Exception:
        logger.exception("Ошибка выполнения рассылки id=%s", broadcast_id)
        factory = get_session_factory()
        async with factory() as session:
            bc = await session.get(Broadcast, broadcast_id)
            if bc and bc.status in ("pending", "running"):
                bc.status = "failed"
                await session.commit()


@app.post("/admin/broadcasts")
async def create_broadcast(
    body: BroadcastCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    admin=Depends(admin_auth),
):
    if not body.message_text.strip():
        raise HTTPException(400, "Пустое сообщение")

    filters_payload = None
    if body.filters is not None:
        filters_payload = body.filters.model_dump(exclude_none=True)
    elif body.filters_json:
        try:
            filters_payload = json.loads(body.filters_json)
        except json.JSONDecodeError as e:
            raise HTTPException(400, "Неверный filters_json") from e

    bc = Broadcast(
        admin_id=admin["id"],
        message_text=body.message_text.strip(),
        filters_json=json.dumps(filters_payload, ensure_ascii=False) if filters_payload else None,
        target_user_ids=json.dumps(body.target_user_ids) if body.target_user_ids else None,
    )
    session.add(bc)
    await session.flush()
    broadcast_id = bc.id
    await session.commit()

    background_tasks.add_task(_run_broadcast_job, broadcast_id)
    return {"id": broadcast_id, "status": "pending"}


@app.post("/admin/broadcasts/{broadcast_id}/send")
async def send_broadcast_now(
    broadcast_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_auth),
):
    """Запустить (или повторить) отправку рассылки."""
    bc = await session.get(Broadcast, broadcast_id)
    if not bc:
        raise HTTPException(404, "Рассылка не найдена")
    if bc.status == "running":
        raise HTTPException(400, "Рассылка уже отправляется")
    if bc.status == "completed":
        # Повторная отправка: сбрасываем в pending
        pass
    bc.status = "pending"
    bc.sent_count = 0
    bc.total_count = 0
    await session.commit()
    background_tasks.add_task(_run_broadcast_job, broadcast_id)
    return {"ok": True, "id": broadcast_id, "status": "pending"}


@app.get("/admin/payments")
async def admin_payments(
    provider: str | None = Query(None),
    status: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_auth),
):
    stmt = select(Payment).order_by(Payment.id.desc()).limit(150)
    clauses = []
    if provider:
        clauses.append(Payment.provider == provider)
    if status:
        clauses.append(Payment.status == status)
    if clauses:
        stmt = select(Payment).where(*clauses).order_by(Payment.id.desc()).limit(150)

    result = await session.execute(stmt)
    out = []
    for p in result.scalars().all():
        user = await session.get(User, p.user_id)
        out.append(
            {
                "id": p.id,
                "user_id": p.user_id,
                "user": _user_brief(user),
                "provider": p.provider,
                "external_id": p.external_id,
                "amount_sparks": p.amount_sparks,
                "amount_rub": p.amount_rub,
                "status": p.status,
                "purpose": p.purpose,
                "is_stub": p.is_stub,
                "created_at": str(p.created_at) if p.created_at else None,
                "paid_at": str(p.paid_at) if p.paid_at else None,
            }
        )
    return out


@app.get("/admin/settings")
async def get_settings_api(session: AsyncSession = Depends(get_session), _=Depends(admin_auth)):
    values = await get_all_settings(session)
    return {"values": values, "meta": SETTING_META, "defaults": env_defaults()}


class SettingUpdate(BaseModel):
    key: str
    value: str


class SettingsBulkUpdate(BaseModel):
    values: dict[str, str]


@app.put("/admin/settings")
async def update_setting(
    body: SettingUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_auth),
):
    if body.key not in env_defaults():
        raise HTTPException(400, f"Неизвестный ключ: {body.key}")
    await upsert_setting(session, body.key, body.value.strip())
    return {"ok": True}


@app.put("/admin/settings/bulk")
async def update_settings_bulk(
    body: SettingsBulkUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_auth),
):
    defaults = env_defaults()
    for key, value in body.values.items():
        if key not in defaults:
            raise HTTPException(400, f"Неизвестный ключ: {key}")
        await upsert_setting(session, key, str(value).strip())
    return {"ok": True}


@app.get("/admin/events")
async def admin_events(session: AsyncSession = Depends(get_session), _=Depends(admin_auth)):
    result = await session.execute(
        select(Event).where(Event.status != "deleted").order_by(Event.id.desc()).limit(100)
    )
    out = []
    for e in result.scalars().all():
        organizer = await session.get(User, e.organizer_id)
        out.append(
            {
                "id": e.id,
                "title": e.title,
                "status": e.status,
                "city": e.city,
                "address": e.address,
                "event_date": e.event_date,
                "event_time": e.event_time,
                "price": e.price,
                "men_needed": e.men_needed,
                "women_needed": e.women_needed,
                "men_count": e.men_count,
                "women_count": e.women_count,
                "category": e.category,
                "description": e.description,
                "photo_file_id": e.photo_file_id,
                "organizer": _user_brief(organizer),
                "created_at": str(e.created_at) if e.created_at else None,
            }
        )
    return out


class EventUpdate(BaseModel):
    status: str  # closed, deleted


@app.patch("/admin/events/{event_id}")
async def update_event(
    event_id: int,
    body: EventUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_auth),
):
    if body.status not in ("closed", "deleted", "active"):
        raise HTTPException(400, "Неверный статус")
    event = await session.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Тусовка не найдена")
    event.status = body.status
    return {"ok": True, "status": event.status}


@app.get("/admin/withdraws")
async def admin_withdraws(
    status: str | None = Query("pending"),
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_auth),
):
    stmt = select(WithdrawRequest).order_by(WithdrawRequest.id.desc()).limit(100)
    if status:
        stmt = (
            select(WithdrawRequest)
            .where(WithdrawRequest.status == status)
            .order_by(WithdrawRequest.id.desc())
            .limit(100)
        )
    result = await session.execute(stmt)
    out = []
    for w in result.scalars().all():
        user = await session.get(User, w.user_id)
        out.append(
            {
                "id": w.id,
                "user_id": w.user_id,
                "user": _user_brief(user),
                "amount": w.amount,
                "fee": w.fee,
                "net_amount": w.net_amount,
                "requisites": w.requisites,
                "method": getattr(w, "method", None) or "requisites",
                "status": w.status,
                "created_at": str(w.created_at) if w.created_at else None,
            }
        )
    return out


class WithdrawDecision(BaseModel):
    decision: str  # completed, rejected


@app.patch("/admin/withdraws/{withdraw_id}")
async def resolve_withdraw(
    withdraw_id: int,
    body: WithdrawDecision,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_auth),
):
    if body.decision not in ("completed", "rejected"):
        raise HTTPException(400, "Неверное решение")

    req = await session.get(WithdrawRequest, withdraw_id)
    if not req:
        raise HTTPException(404, "Заявка не найдена")
    if req.status not in ("pending", "processing"):
        raise HTTPException(400, "Заявка уже обработана")

    user = await session.get(User, req.user_id)

    if body.decision == "completed":
        # Для Stars — реальная выплата подарками, если ещё не выполнена
        method = getattr(req, "method", None) or "requisites"
        if method == "stars" and user and settings.bot_token:
            from aiogram import Bot
            from services.stars_payout_service import payout_stars_via_gifts

            bot = Bot(token=settings.bot_token)
            try:
                result = await payout_stars_via_gifts(
                    bot,
                    user.telegram_id,
                    req.net_amount,
                    note=f"LUMA withdraw #{req.id}",
                )
            finally:
                await bot.session.close()
            if not result.ok:
                raise HTTPException(400, f"Stars payout failed: {result.error}")
            req.payout_meta = f"gifts={result.gifts_sent};stars={result.stars_spent}"
        req.status = "completed"
        notify_text = (
            f"✅ Вывод {req.amount} Искр выполнен.\n"
            f"К выплате: {req.net_amount} ({'Stars' if method == 'stars' else 'реквизиты'}; комиссия {req.fee})."
        )
    else:
        req.status = "rejected"
        await add_transaction(session, req.user_id, req.amount, "withdraw_refund", req.id)
        notify_text = (
            f"❌ Заявка на вывод {req.amount} Искр отклонена.\n"
            f"Искры возвращены на баланс."
        )

    if user and settings.bot_token:
        from aiogram import Bot

        bot = Bot(token=settings.bot_token)
        try:
            await bot.send_message(user.telegram_id, notify_text)
        except Exception:
            pass
        finally:
            await bot.session.close()

    return {"ok": True, "status": req.status, "method": getattr(req, "method", None)}


# --- Premium / Sparks / Referrals / Bloggers ---

@app.get("/admin/premium")
async def admin_premium(session: AsyncSession = Depends(get_session), _=Depends(admin_auth)):
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(User).where(User.premium_until.is_not(None)).order_by(User.premium_until.desc()).limit(200)
    )
    out = []
    for u in result.scalars().all():
        until = u.premium_until
        if until and until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        active = bool(until and until > now)
        forever = bool(until and until.year >= 2099)
        out.append(
            {
                "id": u.id,
                "telegram_id": u.telegram_id,
                "display_name": u.display_name,
                "username": u.username,
                "city": u.city,
                "sparks_balance": u.sparks_balance,
                "premium": is_premium(u),
                "premium_until": str(u.premium_until) if u.premium_until else None,
                "active": active,
                "forever": forever,
            }
        )
    return out


class PremiumGrant(BaseModel):
    user_id: int
    days: int = 30  # -1 forever, 0 revoke


@app.post("/admin/premium/grant")
async def admin_premium_grant(
    body: PremiumGrant,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_auth),
):
    user = await session.get(User, body.user_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    now = datetime.now(timezone.utc)
    if body.days == 0:
        user.premium_until = None
    elif body.days < 0:
        user.premium_until = datetime(2099, 12, 31, tzinfo=timezone.utc)
    else:
        base = user.premium_until if user.premium_until and user.premium_until > now else now
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
        user.premium_until = base + timedelta(days=body.days)
    return {"ok": True, "premium_until": str(user.premium_until) if user.premium_until else None}


@app.get("/admin/sparks")
async def admin_sparks(
    tx_type: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_auth),
):
    # Покупки в ledger пишутся как purchase; buy_sparks — алиас из платежей
    type_aliases = {
        "buy_sparks": ["purchase", "buy_sparks"],
        "purchase": ["purchase", "buy_sparks"],
    }
    stmt = select(SparksTransaction).order_by(SparksTransaction.id.desc()).limit(200)
    if tx_type:
        types = type_aliases.get(tx_type, [tx_type])
        stmt = (
            select(SparksTransaction)
            .where(SparksTransaction.tx_type.in_(types))
            .order_by(SparksTransaction.id.desc())
            .limit(200)
        )
    result = await session.execute(stmt)
    out = []
    for tx in result.scalars().all():
        user = await session.get(User, tx.user_id)
        out.append(
            {
                "id": tx.id,
                "user_id": tx.user_id,
                "user": _user_brief(user),
                "amount": tx.amount,
                "tx_type": tx.tx_type,
                "reference_id": tx.reference_id,
                "created_at": str(tx.created_at) if tx.created_at else None,
            }
        )
    return out


class SparksAdjust(BaseModel):
    user_id: int
    amount: int
    reason: str = "admin_adjust"


@app.post("/admin/sparks/adjust")
async def admin_sparks_adjust(
    body: SparksAdjust,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_auth),
):
    user = await session.get(User, body.user_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    await add_transaction(session, user.id, body.amount, body.reason or "admin_adjust")
    return {"ok": True, "sparks_balance": user.sparks_balance}


@app.get("/admin/referrals")
async def admin_referrals(session: AsyncSession = Depends(get_session), _=Depends(admin_auth)):
    result = await session.execute(
        select(User).where(User.referral_count > 0).order_by(User.referral_count.desc()).limit(200)
    )
    out = []
    for u in result.scalars().all():
        rewards = (
            await session.execute(
                select(ReferralReward).where(ReferralReward.user_id == u.id).order_by(ReferralReward.id.desc())
            )
        ).scalars().all()
        out.append(
            {
                "id": u.id,
                "display_name": u.display_name,
                "username": u.username,
                "telegram_id": u.telegram_id,
                "referral_code": u.referral_code,
                "referral_count": u.referral_count,
                "referral_track": u.referral_track,
                "rewards": [
                    {
                        "threshold": r.threshold,
                        "reward_type": r.reward_type,
                        "claimed_at": str(r.claimed_at) if r.claimed_at else None,
                    }
                    for r in rewards
                ],
            }
        )
    return out


@app.get("/admin/bloggers")
async def admin_bloggers(session: AsyncSession = Depends(get_session), _=Depends(admin_auth)):
    result = await session.execute(select(BloggerProfile).order_by(BloggerProfile.id.desc()).limit(200))
    out = []
    for bp in result.scalars().all():
        user = await session.get(User, bp.user_id)
        out.append(
            {
                "id": bp.id,
                "user_id": bp.user_id,
                "user": _user_brief(user),
                "status": bp.status,
                "views": bp.views,
                "total_commission": bp.total_commission,
                "reward_500k_claimed": bp.reward_500k_claimed,
                "reward_1m_claimed": bp.reward_1m_claimed,
                "created_at": str(bp.created_at) if bp.created_at else None,
            }
        )
    return out


class BloggerDecision(BaseModel):
    decision: str  # approve / reject
    views: int | None = None


@app.patch("/admin/bloggers/{user_id}")
async def admin_blogger_decide(
    user_id: int,
    body: BloggerDecision,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_auth),
):
    if body.decision == "approve":
        await approve_blogger(session, user_id)
    elif body.decision == "reject":
        await reject_blogger(session, user_id)
    else:
        raise HTTPException(400, "Неверное решение")
    if body.views is not None:
        result = await session.execute(select(BloggerProfile).where(BloggerProfile.user_id == user_id))
        bp = result.scalar_one_or_none()
        if bp:
            bp.views = max(0, body.views)
            from services.blogger_service import _maybe_claim_view_rewards

            user = await session.get(User, user_id)
            if user:
                await _maybe_claim_view_rewards(session, user, bp)
    return {"ok": True}


@app.post("/payments/yookassa/webhook")
async def yookassa_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    """Webhook ЮKassa: зачисление искр при payment.succeeded."""
    payload = await request.json()
    from services.yookassa_service import handle_yookassa_webhook

    payment, newly_credited = await handle_yookassa_webhook(session, payload)
    if payment and newly_credited:
        user = await session.get(User, payment.user_id)
        if user and settings.bot_token:
            from aiogram import Bot

            bot = Bot(token=settings.bot_token)
            try:
                await bot.send_message(
                    user.telegram_id,
                    f"Зачислено {payment.amount_sparks} Искр на баланс!",
                )
            except Exception:
                pass
            finally:
                await bot.session.close()
    return {"ok": True}
