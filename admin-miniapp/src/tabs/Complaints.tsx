import { useEffect, useMemo, useState } from 'react'
import { api, formatName, shortDate, type ComplaintItem } from '../api'
import { EventDetail } from '../components/EventDetail'
import { EmptyState, ErrorState, LoadingState } from '../components/Shell'
import { UserProfile } from '../components/UserProfile'
import { COMPLAINT_TYPE, label } from '../labels'

interface Props {
  toast: (msg: string, type?: 'success' | 'error') => void
}

type EventFilter = 'all' | 'events' | number

interface EventStat {
  eventId: number
  title: string
  complaints: number
  reporters: number
}

export function Complaints({ toast }: Props) {
  const [items, setItems] = useState<ComplaintItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState<number | null>(null)
  const [viewUserId, setViewUserId] = useState<number | null>(null)
  const [viewEventId, setViewEventId] = useState<number | null>(null)
  const [eventFilter, setEventFilter] = useState<EventFilter>('all')

  async function load() {
    setLoading(true)
    setError('')
    try {
      setItems(await api<ComplaintItem[]>('/admin/complaints'))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const eventStats = useMemo(() => {
    const map = new Map<number, { title: string; reporters: Set<number> }>()
    for (const c of items) {
      if (!c.event_id) continue
      let row = map.get(c.event_id)
      if (!row) {
        row = { title: c.event_title || `Тусовка #${c.event_id}`, reporters: new Set() }
        map.set(c.event_id, row)
      }
      if (c.reporter?.id) row.reporters.add(c.reporter.id)
      else row.reporters.add(-c.id) // жалоба без reporter всё равно считается
    }
    const list: EventStat[] = [...map.entries()].map(([eventId, row]) => ({
      eventId,
      title: row.title,
      complaints: items.filter((c) => c.event_id === eventId).length,
      reporters: row.reporters.size,
    }))
    list.sort((a, b) => b.reporters - a.reporters || b.complaints - a.complaints || a.title.localeCompare(b.title))
    return list
  }, [items])

  const eventCountById = useMemo(() => {
    const m = new Map<number, EventStat>()
    for (const s of eventStats) m.set(s.eventId, s)
    return m
  }, [eventStats])

  const filtered = useMemo(() => {
    let list = items
    if (eventFilter === 'events') {
      list = items.filter((c) => c.event_id != null)
    } else if (typeof eventFilter === 'number') {
      list = items.filter((c) => c.event_id === eventFilter)
    }
    return [...list].sort((a, b) => {
      const ca = a.event_id ? eventCountById.get(a.event_id)?.reporters ?? 0 : 0
      const cb = b.event_id ? eventCountById.get(b.event_id)?.reporters ?? 0 : 0
      if (cb !== ca) return cb - ca
      return b.id - a.id
    })
  }, [items, eventFilter, eventCountById])

  async function resolve(id: number, decision: string) {
    if (decision === 'block' && !confirm('Заблокировать пользователя?')) return
    setBusy(id)
    try {
      await api(`/admin/complaints/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ decision }),
      })
      toast(
        decision === 'block'
          ? 'Пользователь заблокирован'
          : decision === 'warning'
            ? 'Предупреждение выдано'
            : 'Жалоба отклонена',
      )
      await load()
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), 'error')
    } finally {
      setBusy(null)
    }
  }

  if (viewUserId) {
    return (
      <UserProfile
        userId={viewUserId}
        toast={toast}
        backLabel="← К жалобам"
        onBack={() => setViewUserId(null)}
      />
    )
  }

  if (viewEventId) {
    return (
      <EventDetail
        eventId={viewEventId}
        toast={toast}
        backLabel="← К жалобам"
        onBack={() => setViewEventId(null)}
      />
    )
  }

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} onRetry={load} />

  return (
    <div>
      <h2 className="section-title">Жалобы</h2>
      <p className="section-desc">Очередь на модерацию</p>

      {eventStats.length > 0 && (
        <div className="card" style={{ marginBottom: 12 }}>
          <div className="detail-label" style={{ marginBottom: 10 }}>
            Фильтр по тусовкам
          </div>
          <div className="chips">
            <button
              type="button"
              className={`chip${eventFilter === 'all' ? ' active' : ''}`}
              onClick={() => setEventFilter('all')}
            >
              Все ({items.length})
            </button>
            <button
              type="button"
              className={`chip${eventFilter === 'events' ? ' active' : ''}`}
              onClick={() => setEventFilter('events')}
            >
              На тусовки ({eventStats.reduce((n, s) => n + s.complaints, 0)})
            </button>
            {eventStats.map((s) => (
              <button
                key={s.eventId}
                type="button"
                className={`chip${eventFilter === s.eventId ? ' active' : ''}`}
                onClick={() => setEventFilter(s.eventId)}
                title={`${s.complaints} жалоб · ${s.reporters} чел.`}
              >
                {s.title.length > 22 ? `${s.title.slice(0, 20)}…` : s.title}
                <span className={`badge${s.reporters > 1 ? ' warning' : ' muted'}`} style={{ marginLeft: 6 }}>
                  {s.reporters} чел.
                </span>
              </button>
            ))}
          </div>
          {eventStats.some((s) => s.reporters > 1) && (
            <p className="row-meta" style={{ marginTop: 10 }}>
              Несколько жалоб на одну тусовку:{' '}
              {eventStats
                .filter((s) => s.reporters > 1)
                .map((s) => `${s.title} (${s.reporters})`)
                .join(' · ')}
            </p>
          )}
        </div>
      )}

      {filtered.length === 0 && <EmptyState title="Очередь пуста" desc="Нет жалоб по выбранному фильтру" />}

      {filtered.map((c) => {
        const stat = c.event_id ? eventCountById.get(c.event_id) : undefined
        return (
          <div key={c.id} className="card row-card">
            <div className="row-top">
              <div>
                <div className="row-title">#{c.id}</div>
                <div className="row-meta">{shortDate(c.created_at)}</div>
              </div>
              <div className="badges">
                <span className="badge">{label(COMPLAINT_TYPE, c.type)}</span>
                {stat && stat.reporters > 1 && (
                  <span className="badge warning">
                    {stat.reporters} чел. · {stat.complaints} жал.
                  </span>
                )}
              </div>
            </div>
            <div className="row-meta">
              От:{' '}
              {c.reporter ? (
                <button type="button" className="text-link" onClick={() => setViewUserId(c.reporter!.id)}>
                  {formatName(c.reporter)}
                </button>
              ) : (
                '—'
              )}
              {c.target_user && (
                <>
                  {' '}
                  · На:{' '}
                  <button type="button" className="text-link" onClick={() => setViewUserId(c.target_user!.id)}>
                    {formatName(c.target_user)}
                  </button>
                </>
              )}
              {c.event_id && (
                <>
                  {' '}
                  · Тусовка:{' '}
                  <button type="button" className="text-link" onClick={() => setViewEventId(c.event_id!)}>
                    {c.event_title || `Тусовка #${c.event_id}`}
                  </button>
                </>
              )}
            </div>
            <div className="row-body">{c.text}</div>
            <div className="row-actions">
              {c.target_user && (
                <button
                  type="button"
                  className="btn btn-sm btn-ghost"
                  onClick={() => setViewUserId(c.target_user!.id)}
                >
                  Анкета
                </button>
              )}
              {c.reporter && (
                <button
                  type="button"
                  className="btn btn-sm btn-ghost"
                  onClick={() => setViewUserId(c.reporter!.id)}
                >
                  Кто пожаловался
                </button>
              )}
              {c.event_id && (
                <button
                  type="button"
                  className="btn btn-sm btn-ghost"
                  onClick={() => setViewEventId(c.event_id!)}
                >
                  Тусовка
                </button>
              )}
              {stat && stat.reporters > 1 && (
                <button
                  type="button"
                  className="btn btn-sm btn-warn"
                  onClick={() => setEventFilter(c.event_id!)}
                >
                  Все на эту ({stat.reporters})
                </button>
              )}
              <button
                type="button"
                className="btn btn-sm btn-danger"
                disabled={busy === c.id}
                onClick={() => resolve(c.id, 'block')}
              >
                Блок
              </button>
              <button
                type="button"
                className="btn btn-sm btn-warn"
                disabled={busy === c.id}
                onClick={() => resolve(c.id, 'warning')}
              >
                Предупреждение
              </button>
              <button
                type="button"
                className="btn btn-sm btn-ghost"
                disabled={busy === c.id}
                onClick={() => resolve(c.id, 'reject')}
              >
                Отклонить
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
