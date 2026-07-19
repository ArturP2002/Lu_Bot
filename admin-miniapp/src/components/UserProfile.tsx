import { useEffect, useState, type ReactNode } from 'react'
import { api, mediaHeaders, mediaUrl, shortDate, type UserDetail } from '../api'
import { LoadingState } from './Shell'
import {
  label,
  PAYMENT_PROVIDER,
  PAYMENT_STATUS,
  REFERRAL_TRACK,
  TX_TYPE,
} from '../labels'

const GENDER: Record<string, string> = { male: 'Мужской', female: 'Женский', other: 'Другой' }
const SEEKING: Record<string, string> = { men: 'Мужчины', women: 'Женщины', both: 'Оба' }
const VISIBLE: Record<string, string> = { men: 'Мужчинам', women: 'Женщинам', all: 'Всем' }
const COUNTRY: Record<string, string> = {
  russia: 'Россия',
  belarus: 'Беларусь',
  kazakhstan: 'Казахстан',
  ukraine: 'Украина',
  other: 'Другое',
}

function DetailRow({ label: title, value }: { label: string; value: ReactNode }) {
  return (
    <div className="detail-row">
      <span className="detail-label">{title}</span>
      <span className="detail-value">{value || '—'}</span>
    </div>
  )
}

function ProfilePhoto({ fileId }: { fileId: string }) {
  const [src, setSrc] = useState<string | null>(null)

  useEffect(() => {
    let revoked: string | null = null
    let cancelled = false
    async function load() {
      try {
        const res = await fetch(mediaUrl(fileId), { headers: mediaHeaders() })
        if (!res.ok) throw new Error('fail')
        const blob = await res.blob()
        if (cancelled) return
        const url = URL.createObjectURL(blob)
        revoked = url
        setSrc(url)
      } catch {
        /* ignore */
      }
    }
    load()
    return () => {
      cancelled = true
      if (revoked) URL.revokeObjectURL(revoked)
    }
  }, [fileId])

  if (!src) return null
  return <img className="media-preview profile-photo" src={src} alt="Фото анкеты" />
}

interface Props {
  userId: number
  toast: (msg: string, type?: 'success' | 'error') => void
  onBack: () => void
  backLabel?: string
}

export function UserProfile({ userId, toast, onBack, backLabel = '← Назад' }: Props) {
  const [detail, setDetail] = useState<UserDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  async function load() {
    setLoading(true)
    try {
      setDetail(await api<UserDetail>(`/admin/users/${userId}`))
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), 'error')
      onBack()
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [userId])

  async function toggleBan() {
    if (!detail) return
    setBusy(true)
    try {
      await api(`/admin/users/${detail.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_banned: !detail.is_banned }),
      })
      toast(detail.is_banned ? 'Пользователь разбанен' : 'Пользователь заблокирован')
      await load()
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), 'error')
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <LoadingState />
  if (!detail) return null

  return (
    <div>
      <button type="button" className="btn btn-ghost btn-sm" style={{ marginBottom: 12 }} onClick={onBack}>
        {backLabel}
      </button>

      <h2 className="section-title">{detail.display_name || detail.username || `User #${detail.id}`}</h2>
      <p className="section-desc">
        {detail.username ? `@${detail.username} · ` : ''}tg {detail.telegram_id}
      </p>

      <div className="badges" style={{ marginBottom: 14 }}>
        {detail.verified && <span className="badge success">Верифицирован</span>}
        {detail.premium && <span className="badge">Premium</span>}
        {detail.is_banned && <span className="badge danger">Заблокирован</span>}
        {detail.disabled && <span className="badge muted">Скрыт</span>}
        {detail.warning_count > 0 && <span className="badge warning">⚠ {detail.warning_count}</span>}
      </div>

      {detail.photo_file_id && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <ProfilePhoto fileId={detail.photo_file_id} />
        </div>
      )}

      <div className="card">
        <DetailRow label="Баланс" value={<span className="hl mono">{detail.sparks_balance} искр</span>} />
        <DetailRow
          label="Город"
          value={[detail.city, label(COUNTRY, detail.country, detail.country || undefined)].filter(Boolean).join(', ')}
        />
        <DetailRow label="Возраст" value={detail.age} />
        <DetailRow label="Пол" value={GENDER[detail.gender || ''] || detail.gender} />
        <DetailRow label="Ищет" value={SEEKING[detail.seeking || ''] || detail.seeking} />
        <DetailRow label="Виден" value={VISIBLE[detail.visible_to || ''] || detail.visible_to} />
        <DetailRow label="Телефон" value={detail.contact_phone} />
        <DetailRow label="Рейтинг" value={`${detail.rating_avg} (${detail.rating_count})`} />
        <DetailRow label="Тусовки" value={`был ${detail.events_attended} · орг. ${detail.events_organized}`} />
        <DetailRow label="Premium до" value={detail.premium_until ? shortDate(detail.premium_until) : '—'} />
        <DetailRow
          label="Реферал"
          value={`${detail.referral_code || '—'} · ${detail.referral_count} · ${label(REFERRAL_TRACK, detail.referral_track)}`}
        />
        <DetailRow label="Создан" value={shortDate(detail.created_at)} />
      </div>

      {detail.bio && (
        <div className="card">
          <div className="detail-label" style={{ marginBottom: 8 }}>
            О себе
          </div>
          <div className="row-body">{detail.bio}</div>
        </div>
      )}

      {detail.goal && (
        <div className="card">
          <div className="detail-label" style={{ marginBottom: 8 }}>
            Цель
          </div>
          <div className="row-title">{detail.goal.title}</div>
          <div className="row-meta mono">
            {detail.goal.collected_sparks} / {detail.goal.target_sparks} искр
          </div>
        </div>
      )}

      <div className="card">
        <div className="detail-label" style={{ marginBottom: 10 }}>
          Последние платежи
        </div>
        {detail.recent_payments.length === 0 && <p className="row-meta">Нет платежей</p>}
        {detail.recent_payments.map((p) => (
          <div key={p.id} className="mini-row">
            <span>{label(PAYMENT_PROVIDER, p.provider)}</span>
            <span className="mono">{p.amount_sparks} искр</span>
            <span className={`badge ${p.status === 'succeeded' ? 'success' : 'muted'}`}>
              {label(PAYMENT_STATUS, p.status)}
            </span>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="detail-label" style={{ marginBottom: 10 }}>
          История Искр
        </div>
        {detail.recent_transactions.length === 0 && <p className="row-meta">Нет транзакций</p>}
        {detail.recent_transactions.map((t) => (
          <div key={t.id} className="mini-row">
            <span>{label(TX_TYPE, t.tx_type)}</span>
            <span className={`mono ${t.amount >= 0 ? 'hl' : ''}`}>
              {t.amount > 0 ? '+' : ''}
              {t.amount}
            </span>
            <span className="row-meta">{shortDate(t.created_at)}</span>
          </div>
        ))}
      </div>

      <div className="row-actions" style={{ marginTop: 8 }}>
        <button
          type="button"
          className={`btn ${detail.is_banned ? 'btn-success' : 'btn-danger'}`}
          disabled={busy}
          onClick={toggleBan}
        >
          {detail.is_banned ? 'Разбанить' : 'Забанить'}
        </button>
      </div>
    </div>
  )
}
