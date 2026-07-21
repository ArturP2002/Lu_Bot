import { useEffect, useMemo, useState } from 'react'
import { api, shortDate } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/Shell'

interface PremiumUser {
  id: number
  telegram_id: number
  display_name: string | null
  username: string | null
  city: string | null
  sparks_balance: number
  premium: boolean
  premium_until: string | null
  active: boolean
  forever: boolean
}

type StatusFilter = 'all' | 'active' | 'expired' | 'forever'

interface Props {
  toast: (message: string, type?: 'success' | 'error') => void
}

const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'active', label: 'Активные' },
  { value: 'expired', label: 'Истёкшие' },
  { value: 'forever', label: 'Навсегда' },
]

function daysLeft(until: string | null, forever: boolean): string | null {
  if (!until || forever) return null
  const end = new Date(until)
  if (Number.isNaN(end.getTime())) return null
  const ms = end.getTime() - Date.now()
  if (ms <= 0) return 'срок истёк'
  const days = Math.ceil(ms / (1000 * 60 * 60 * 24))
  if (days === 1) return 'остался 1 день'
  if (days < 5) return `осталось ${days} дня`
  return `осталось ${days} дн.`
}

function matchesQuery(u: PremiumUser, q: string): boolean {
  if (!q) return true
  const hay = [String(u.id), String(u.telegram_id), u.display_name || '', u.username || '', u.city || '']
    .join(' ')
    .toLowerCase()
  return hay.includes(q)
}

export function Premium({ toast }: Props) {
  const [items, setItems] = useState<PremiumUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [userId, setUserId] = useState('')
  const [days, setDays] = useState('30')
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<StatusFilter>('all')
  const [busy, setBusy] = useState(false)

  async function load() {
    setLoading(true)
    setError('')
    try {
      setItems(await api<PremiumUser[]>('/admin/premium'))
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
    return items.filter((u) => {
      if (!matchesQuery(u, q)) return false
      if (status === 'active') return u.active && !u.forever
      if (status === 'expired') return !u.active
      if (status === 'forever') return u.forever
      return true
    })
  }, [items, query, status])

  async function grant() {
    if (!userId.trim()) {
      toast('Укажите ID пользователя', 'error')
      return
    }
    setBusy(true)
    try {
      await api('/admin/premium/grant', {
        method: 'POST',
        body: JSON.stringify({ telegram_id: Number(userId), days: Number(days) }),
      })
      toast('Подписка обновлена')
      setUserId('')
      await load()
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), 'error')
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} onRetry={load} />

  const activeCount = items.filter((u) => u.active).length

  return (
    <div>
      <h2 className="section-title">Premium</h2>
      <p className="section-desc">Выдача и продление подписок · {activeCount} активных из {items.length}</p>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="form-grid">
          <div className="form-grid-2">
            <div className="field" style={{ marginBottom: 0 }}>
              <label>Telegram ID пользователя</label>
              <input
                className="input"
                inputMode="numeric"
                placeholder="Telegram ID"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
              />
            </div>
            <div className="field" style={{ marginBottom: 0 }}>
              <label>Срок, дней</label>
              <input
                className="input"
                inputMode="numeric"
                placeholder="30"
                value={days}
                onChange={(e) => setDays(e.target.value)}
              />
            </div>
          </div>
          <p className="form-hint">
            30 — продлить на месяц · −1 — навсегда · 0 — снять Premium
          </p>
          <button type="button" className="btn btn-primary btn-block" disabled={busy} onClick={grant}>
            {busy ? 'Сохранение…' : 'Выдать / обновить'}
          </button>
        </div>
      </div>

      <div className="search-bar">
        <input
          className="input"
          placeholder="Поиск: имя, @username, ID или Telegram ID"
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
          title={items.length ? 'Ничего не найдено' : 'Нет Premium-пользователей'}
          desc={items.length ? 'Измените поиск или фильтр' : undefined}
        />
      ) : (
        filtered.map((u) => {
          const left = daysLeft(u.premium_until, u.forever)
          return (
            <div key={u.id} className="card row-card">
              <div className="row-top">
                <div>
                  <div className="row-title">{u.display_name || u.username || `Пользователь #${u.id}`}</div>
                  <div className="row-meta">
                    #{u.id}
                    {u.username ? ` · @${u.username}` : ''}
                    {` · tg ${u.telegram_id}`}
                    {u.city ? ` · ${u.city}` : ''}
                  </div>
                </div>
                <div className="badges">
                  {u.forever ? (
                    <span className="badge">Навсегда</span>
                  ) : u.active ? (
                    <span className="badge success">Активен</span>
                  ) : (
                    <span className="badge muted">Истёк</span>
                  )}
                </div>
              </div>
              <div className="detail-row">
                <span className="detail-label">Действует до</span>
                <span className="detail-value mono">
                  {u.forever ? 'Без срока' : shortDate(u.premium_until) || '—'}
                  {left ? ` · ${left}` : ''}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Баланс искр</span>
                <span className="detail-value mono">
                  <span className="hl">{u.sparks_balance ?? 0}</span>
                </span>
              </div>
            </div>
          )
        })
      )}
    </div>
  )
}
