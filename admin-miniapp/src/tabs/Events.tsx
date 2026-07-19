import { useEffect, useState } from 'react'
import { api, formatName, mediaHeaders, mediaUrl, shortDate, type EventItem } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/Shell'
import { EVENT_STATUS, label } from '../labels'

interface Props {
  toast: (msg: string, type?: 'success' | 'error') => void
}

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

export function Events({ toast }: Props) {
  const [items, setItems] = useState<EventItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState<number | null>(null)

  async function load() {
    setLoading(true)
    setError('')
    try {
      setItems(await api<EventItem[]>('/admin/events'))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function setStatus(id: number, status: string) {
    if (status === 'deleted' && !confirm('Удалить тусовку?')) return
    setBusy(id)
    try {
      await api(`/admin/events/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      })
      toast(status === 'closed' ? 'Тусовка закрыта' : status === 'deleted' ? 'Тусовка удалена' : 'Статус обновлён')
      await load()
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), 'error')
    } finally {
      setBusy(null)
    }
  }

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} onRetry={load} />

  return (
    <div>
      <h2 className="section-title">Тусовки</h2>
      <p className="section-desc">Модерация мероприятий</p>

      {items.length === 0 && <EmptyState title="Пока пусто" desc="Тусовок ещё нет" />}

      {items.map((e) => (
        <div key={e.id} className="card row-card">
          <div className="row-top">
            <div>
              <div className="row-title">{e.title}</div>
              <div className="row-meta">
                {e.city}
                {e.event_date ? ` · ${e.event_date}` : ''}
                {e.event_time ? ` ${e.event_time}` : ''}
              </div>
            </div>
            <span className={`badge ${e.status === 'active' ? 'success' : 'muted'}`}>
              {label(EVENT_STATUS, e.status)}
            </span>
          </div>
          <div className="row-meta">
            Организатор: {formatName(e.organizer)}
            {e.category ? ` · ${e.category}` : ''}
            {e.price ? ` · ${e.price} искр` : ' · бесплатно'}
          </div>
          <div className="row-meta mono">
            М {e.men_count}/{e.men_needed} · Ж {e.women_count}/{e.women_needed}
            {e.created_at ? ` · ${shortDate(e.created_at)}` : ''}
          </div>
          {e.description && <div className="row-body">{e.description}</div>}
          {e.photo_file_id && <EventPhoto fileId={e.photo_file_id} />}
          {e.status === 'active' && (
            <div className="row-actions">
              <button type="button" className="btn btn-sm btn-warn" disabled={busy === e.id} onClick={() => setStatus(e.id, 'closed')}>
                Закрыть
              </button>
              <button type="button" className="btn btn-sm btn-danger" disabled={busy === e.id} onClick={() => setStatus(e.id, 'deleted')}>
                Удалить
              </button>
            </div>
          )}
          {e.status === 'closed' && (
            <div className="row-actions">
              <button type="button" className="btn btn-sm btn-ghost" disabled={busy === e.id} onClick={() => setStatus(e.id, 'active')}>
                Открыть снова
              </button>
              <button type="button" className="btn btn-sm btn-danger" disabled={busy === e.id} onClick={() => setStatus(e.id, 'deleted')}>
                Удалить
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
