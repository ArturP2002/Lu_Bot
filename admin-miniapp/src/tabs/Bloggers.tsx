import { useEffect, useMemo, useState } from 'react'
import { api, formatName, shortDate } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/Shell'
import { BLOGGER_STATUS, label } from '../labels'

interface BloggerRow {
  id: number
  user_id: number
  user: { id: number; telegram_id: number; display_name: string | null; username: string | null; city: string | null } | null
  status: string
  total_commission: number
  created_at: string | null
}

type StatusFilter = 'all' | 'approved' | 'rejected'

interface Props {
  toast: (message: string, type?: 'success' | 'error') => void
}

const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'approved', label: 'Активные' },
  { value: 'rejected', label: 'Снятые' },
]

function statusBadgeClass(status: string): string {
  if (status === 'approved') return 'success'
  if (status === 'rejected') return 'danger'
  return 'muted'
}

function formatNum(n: number): string {
  return n.toLocaleString('ru-RU')
}

export function Bloggers({ toast }: Props) {
  const [items, setItems] = useState<BloggerRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<StatusFilter>('all')
  const [busyId, setBusyId] = useState<number | null>(null)

  async function load() {
    setLoading(true)
    setError('')
    try {
      const rows = await api<BloggerRow[]>('/admin/bloggers')
      setItems(rows)
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
      // pending (legacy) показываем в «Снятые» вместе с rejected
      if (status === 'approved' && b.status !== 'approved') return false
      if (status === 'rejected' && b.status === 'approved') return false
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

  async function setStatusAction(userId: number, decision: 'restore' | 'revoke') {
    const confirmMsg =
      decision === 'revoke'
        ? 'Снять статус блогера? Автовыдача по рефералке больше не вернёт его.'
        : 'Вернуть статус блогера?'
    if (!confirm(confirmMsg)) return

    setBusyId(userId)
    try {
      await api(`/admin/bloggers/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify({ decision }),
      })
      toast(decision === 'restore' ? 'Статус блогера возвращён' : 'Статус блогера снят')
      await load()
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), 'error')
    } finally {
      setBusyId(null)
    }
  }

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} onRetry={load} />

  const activeCount = items.filter((b) => b.status === 'approved').length

  return (
    <div>
      <h2 className="section-title">Блогеры</h2>
      <p className="section-desc">
        Партнёры с статусом Блогер · комиссия 15% с Premium
        {activeCount ? ` · ${activeCount} активных` : ''}
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
        <label>Статус</label>
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
          title={items.length ? 'Ничего не найдено' : 'Нет блогеров'}
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
              <span className="detail-label">Комиссия</span>
              <span className="detail-value mono">
                <span className="hl">{formatNum(b.total_commission)}</span> ⚡
              </span>
            </div>
            <div className="detail-row">
              <span className="detail-label">С</span>
              <span className="detail-value mono">{shortDate(b.created_at) || '—'}</span>
            </div>

            <div className="row-actions">
              {b.status === 'approved' ? (
                <button
                  type="button"
                  className="btn btn-danger btn-sm"
                  disabled={busyId === b.user_id}
                  onClick={() => setStatusAction(b.user_id, 'revoke')}
                >
                  Снять статус
                </button>
              ) : (
                <button
                  type="button"
                  className="btn btn-success btn-sm"
                  disabled={busyId === b.user_id}
                  onClick={() => setStatusAction(b.user_id, 'restore')}
                >
                  Вернуть статус
                </button>
              )}
            </div>
          </div>
        ))
      )}
    </div>
  )
}
