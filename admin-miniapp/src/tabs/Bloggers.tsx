import { useEffect, useMemo, useState } from 'react'
import { api, formatName, shortDate } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/Shell'
import { BLOGGER_STATUS, label } from '../labels'

interface BloggerRow {
  id: number
  user_id: number
  user: { id: number; telegram_id: number; display_name: string | null; username: string | null; city: string | null } | null
  status: string
  views: number
  total_commission: number
  reward_500k_claimed: boolean
  reward_1m_claimed: boolean
  created_at: string | null
}

type StatusFilter = 'all' | 'pending' | 'approved' | 'rejected'

interface Props {
  toast: (message: string, type?: 'success' | 'error') => void
}

const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'pending', label: 'На проверке' },
  { value: 'approved', label: 'Одобрены' },
  { value: 'rejected', label: 'Отклонены' },
]

function statusBadgeClass(status: string): string {
  if (status === 'approved') return 'success'
  if (status === 'rejected') return 'danger'
  if (status === 'pending') return 'warning'
  return 'muted'
}

function formatViews(n: number): string {
  return n.toLocaleString('ru-RU')
}

export function Bloggers({ toast }: Props) {
  const [items, setItems] = useState<BloggerRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<StatusFilter>('all')
  const [busyId, setBusyId] = useState<number | null>(null)
  const [viewsEdit, setViewsEdit] = useState<Record<number, string>>({})

  async function load() {
    setLoading(true)
    setError('')
    try {
      const rows = await api<BloggerRow[]>('/admin/bloggers')
      setItems(rows)
      const next: Record<number, string> = {}
      for (const b of rows) next[b.user_id] = String(b.views)
      setViewsEdit(next)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return items.filter((b) => {
      if (status !== 'all' && b.status !== status) return false
      if (!q) return true
      const hay = [
        String(b.id),
        String(b.user_id),
        String(b.user?.telegram_id || ''),
        b.user?.display_name || '',
        b.user?.username || '',
        label(BLOGGER_STATUS, b.status),
      ]
        .join(' ')
        .toLowerCase()
      return hay.includes(q)
    })
  }, [items, query, status])

  async function decide(userId: number, decision: 'approve' | 'reject') {
    setBusyId(userId)
    try {
      await api(`/admin/bloggers/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify({ decision }),
      })
      toast(decision === 'approve' ? 'Заявка одобрена' : 'Заявка отклонена')
      await load()
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), 'error')
    } finally {
      setBusyId(null)
    }
  }

  async function saveViews(userId: number) {
    const raw = viewsEdit[userId]
    const views = Number(raw)
    if (!Number.isFinite(views) || views < 0) {
      toast('Укажите корректное число просмотров', 'error')
      return
    }
    setBusyId(userId)
    try {
      await api(`/admin/bloggers/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify({ decision: 'approve', views }),
      })
      toast('Просмотры обновлены')
      await load()
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), 'error')
    } finally {
      setBusyId(null)
    }
  }

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} onRetry={load} />

  const pendingCount = items.filter((b) => b.status === 'pending').length

  return (
    <div>
      <h2 className="section-title">Блогеры</h2>
      <p className="section-desc">
        Заявки, просмотры и комиссия 20%
        {pendingCount ? ` · ${pendingCount} на проверке` : ''}
      </p>

      <div className="search-bar">
        <input
          className="input"
          placeholder="Поиск: имя, @username или ID"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div className="field">
        <label>Статус заявки</label>
        <div className="chips">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              className={`chip${status === f.value ? ' active' : ''}`}
              onClick={() => setStatus(f.value)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <p className="toolbar-count">
        Показано {filtered.length}
        {filtered.length !== items.length ? ` из ${items.length}` : ''}
      </p>

      {!filtered.length ? (
        <EmptyState
          title={items.length ? 'Ничего не найдено' : 'Нет заявок блогеров'}
          desc={items.length ? 'Измените поиск или фильтр' : undefined}
        />
      ) : (
        filtered.map((b) => (
          <div key={b.id} className="card row-card">
            <div className="row-top">
              <div>
                <div className="row-title">{formatName(b.user)}</div>
                <div className="row-meta">
                  #{b.user_id}
                  {b.user?.username ? ` · @${b.user.username}` : ''}
                  {b.user?.telegram_id ? ` · tg ${b.user.telegram_id}` : ''}
                  {b.user?.city ? ` · ${b.user.city}` : ''}
                </div>
              </div>
              <div className="badges">
                <span className={`badge ${statusBadgeClass(b.status)}`}>
                  {label(BLOGGER_STATUS, b.status)}
                </span>
              </div>
            </div>

            <div className="detail-row">
              <span className="detail-label">Просмотры</span>
              <span className="detail-value mono">{formatViews(b.views)}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Комиссия</span>
              <span className="detail-value mono">
                <span className="hl">{formatViews(b.total_commission)}</span> ⚡
              </span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Заявка от</span>
              <span className="detail-value mono">{shortDate(b.created_at) || '—'}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Награды</span>
              <span className="detail-value">
                <div className="badges" style={{ justifyContent: 'flex-end' }}>
                  <span className={`badge ${b.reward_500k_claimed ? 'success' : 'muted'}`}>
                    500 тыс.{b.reward_500k_claimed ? ' ✓' : ''}
                  </span>
                  <span className={`badge ${b.reward_1m_claimed ? 'success' : 'muted'}`}>
                    1 млн{b.reward_1m_claimed ? ' ✓' : ''}
                  </span>
                </div>
              </span>
            </div>

            {b.status === 'approved' && (
              <div className="form-grid" style={{ marginTop: 4 }}>
                <div className="field" style={{ marginBottom: 0 }}>
                  <label>Обновить просмотры</label>
                  <input
                    className="input"
                    inputMode="numeric"
                    value={viewsEdit[b.user_id] ?? String(b.views)}
                    onChange={(e) => setViewsEdit((prev) => ({ ...prev, [b.user_id]: e.target.value }))}
                  />
                </div>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  disabled={busyId === b.user_id}
                  onClick={() => saveViews(b.user_id)}
                >
                  Сохранить просмотры
                </button>
              </div>
            )}

            {b.status === 'pending' && (
              <div className="row-actions">
                <button
                  type="button"
                  className="btn btn-success btn-sm"
                  disabled={busyId === b.user_id}
                  onClick={() => decide(b.user_id, 'approve')}
                >
                  Одобрить
                </button>
                <button
                  type="button"
                  className="btn btn-danger btn-sm"
                  disabled={busyId === b.user_id}
                  onClick={() => decide(b.user_id, 'reject')}
                >
                  Отклонить
                </button>
              </div>
            )}
          </div>
        ))
      )}
    </div>
  )
}
