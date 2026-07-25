import { useEffect, useState } from 'react'
import { api, formatName, mediaHeaders, mediaUrl, shortDate, type EventItem } from '../api'
import { EVENT_STATUS, label } from '../labels'
import { LoadingState } from './Shell'

function EventPhoto({ fileId }: { fileId: string }) {
  const [src, setSrc] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

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
        if (!cancelled) setFailed(true)
      }
    }

    load()
    return () => {
      cancelled = true
      if (revoked) URL.revokeObjectURL(revoked)
    }
  }, [fileId])

  if (failed) return <p className="row-meta">Фото недоступно</p>
  if (!src) return <div className="spinner" style={{ margin: '12px auto' }} />
  return <img className="media-preview" src={src} alt="Фото тусовки" />
}

interface Props {
  eventId: number
  toast: (msg: string, type?: 'success' | 'error') => void
  onBack: () => void
  backLabel?: string
}

export function EventDetail({ eventId, toast, onBack, backLabel = '← Назад' }: Props) {
  const [detail, setDetail] = useState<EventItem | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  async function load() {
    setLoading(true)
    try {
      setDetail(await api<EventItem>(`/admin/events/${eventId}`))
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), 'error')
      onBack()
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [eventId])

  async function setStatus(status: string) {
    if (status === 'deleted' && !confirm('Удалить тусовку?')) return
    setBusy(true)
    try {
      await api(`/admin/events/${eventId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      })
      toast(status === 'closed' ? 'Тусовка закрыта' : status === 'deleted' ? 'Тусовка удалена' : 'Статус обновлён')
      if (status === 'deleted') {
        onBack()
        return
      }
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

      <h2 className="section-title">{detail.title}</h2>
      <p className="section-desc">
        {detail.city}
        {detail.event_date ? ` · ${detail.event_date}` : ''}
        {detail.event_time ? ` ${detail.event_time}` : ''}
      </p>

      <div className="badges" style={{ marginBottom: 14 }}>
        <span className={`badge ${detail.status === 'active' ? 'success' : 'muted'}`}>
          {label(EVENT_STATUS, detail.status)}
        </span>
      </div>

      <div className="card">
        <div className="detail-row">
          <span className="detail-label">Организатор</span>
          <span className="detail-value">{formatName(detail.organizer)}</span>
        </div>
        <div className="detail-row">
          <span className="detail-label">Адрес</span>
          <span className="detail-value">{detail.address || '—'}</span>
        </div>
        <div className="detail-row">
          <span className="detail-label">Категория</span>
          <span className="detail-value">{detail.category || '—'}</span>
        </div>
        <div className="detail-row">
          <span className="detail-label">Цена</span>
          <span className="detail-value mono">{detail.price ? `${detail.price} искр` : 'бесплатно'}</span>
        </div>
        <div className="detail-row">
          <span className="detail-label">Участники</span>
          <span className="detail-value mono">
            М {detail.men_count}/{detail.men_needed} · Ж {detail.women_count}/{detail.women_needed}
          </span>
        </div>
        <div className="detail-row">
          <span className="detail-label">Создана</span>
          <span className="detail-value">{shortDate(detail.created_at) || '—'}</span>
        </div>
      </div>

      {detail.description && (
        <div className="card">
          <div className="detail-label" style={{ marginBottom: 8 }}>
            Описание
          </div>
          <div className="row-body">{detail.description}</div>
        </div>
      )}

      {detail.photo_file_id && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <EventPhoto fileId={detail.photo_file_id} />
        </div>
      )}

      {detail.status === 'active' && (
        <div className="row-actions" style={{ marginTop: 8 }}>
          <button type="button" className="btn btn-warn" disabled={busy} onClick={() => setStatus('closed')}>
            Закрыть
          </button>
          <button type="button" className="btn btn-danger" disabled={busy} onClick={() => setStatus('deleted')}>
            Удалить
          </button>
        </div>
      )}
      {detail.status === 'closed' && (
        <div className="row-actions" style={{ marginTop: 8 }}>
          <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => setStatus('active')}>
            Открыть снова
          </button>
          <button type="button" className="btn btn-danger" disabled={busy} onClick={() => setStatus('deleted')}>
            Удалить
          </button>
        </div>
      )}
    </div>
  )
}
