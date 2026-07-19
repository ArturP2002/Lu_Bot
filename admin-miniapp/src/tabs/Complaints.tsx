import { useEffect, useState } from 'react'
import { api, formatName, shortDate, type ComplaintItem } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/Shell'
import { UserProfile } from '../components/UserProfile'
import { COMPLAINT_TYPE, label } from '../labels'

interface Props {
  toast: (msg: string, type?: 'success' | 'error') => void
}

export function Complaints({ toast }: Props) {
  const [items, setItems] = useState<ComplaintItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState<number | null>(null)
  const [viewUserId, setViewUserId] = useState<number | null>(null)

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

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} onRetry={load} />

  return (
    <div>
      <h2 className="section-title">Жалобы</h2>
      <p className="section-desc">Очередь на модерацию</p>

      {items.length === 0 && <EmptyState title="Очередь пуста" desc="Новых жалоб нет" />}

      {items.map((c) => (
        <div key={c.id} className="card row-card">
          <div className="row-top">
            <div>
              <div className="row-title">#{c.id}</div>
              <div className="row-meta">{shortDate(c.created_at)}</div>
            </div>
            <span className="badge">{label(COMPLAINT_TYPE, c.type)}</span>
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
            {c.event_title && <> · Тусовка: {c.event_title}</>}
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
      ))}
    </div>
  )
}
