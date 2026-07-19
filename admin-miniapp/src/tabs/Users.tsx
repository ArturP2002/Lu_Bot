import { useEffect, useState } from 'react'
import { api, type AdminUser } from '../api'
import { UserProfile } from '../components/UserProfile'
import { EmptyState, ErrorState, LoadingState } from '../components/Shell'

interface Props {
  toast: (msg: string, type?: 'success' | 'error') => void
  initialUserId?: number | null
  onInitialConsumed?: () => void
}

export function Users({ toast, initialUserId, onInitialConsumed }: Props) {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState<number | null>(null)
  const [viewUserId, setViewUserId] = useState<number | null>(null)

  useEffect(() => {
    if (initialUserId) {
      setViewUserId(initialUserId)
      onInitialConsumed?.()
    }
  }, [initialUserId])

  async function load(query = q) {
    setLoading(true)
    setError('')
    try {
      const path = query.trim() ? `/admin/users?q=${encodeURIComponent(query.trim())}` : '/admin/users'
      setUsers(await api<AdminUser[]>(path))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function toggleBan(u: AdminUser) {
    setBusy(u.id)
    try {
      await api(`/admin/users/${u.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_banned: !u.is_banned }),
      })
      toast(u.is_banned ? 'Пользователь разбанен' : 'Пользователь заблокирован')
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
        backLabel="← К списку"
        onBack={() => {
          setViewUserId(null)
          load()
        }}
      />
    )
  }

  return (
    <div>
      <h2 className="section-title">Пользователи</h2>
      <p className="section-desc">Поиск и модерация аккаунтов</p>

      <div className="search-bar">
        <input
          className="input"
          placeholder="Имя, @username, город или ID"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && load()}
        />
        <button type="button" className="btn btn-primary btn-block" style={{ marginTop: 8 }} onClick={() => load()}>
          Найти
        </button>
      </div>

      {loading && <LoadingState />}
      {!loading && error && <ErrorState message={error} onRetry={() => load()} />}
      {!loading && !error && users.length === 0 && (
        <EmptyState title="Никого не найдено" desc="Попробуйте другой запрос" />
      )}

      {!loading &&
        !error &&
        users.map((u) => (
          <div key={u.id} className="card row-card">
            <div className="row-top">
              <div>
                <div className="row-title">{u.display_name || u.username || `User #${u.id}`}</div>
                <div className="row-meta">
                  {u.username ? `@${u.username} · ` : ''}
                  tg {u.telegram_id}
                  {u.city ? ` · ${u.city}` : ''}
                  {u.age ? ` · ${u.age}` : ''}
                </div>
              </div>
              <div className="badges">
                {u.verified && <span className="badge success">Верифицирован</span>}
                {u.premium && <span className="badge">Premium</span>}
                {u.is_banned && <span className="badge danger">Заблокирован</span>}
                {u.warning_count > 0 && <span className="badge warning">⚠ {u.warning_count}</span>}
              </div>
            </div>
            <div className="row-meta mono">
              Баланс: <span className="hl">{u.sparks_balance}</span> искр
            </div>
            <div className="row-actions">
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => setViewUserId(u.id)}>
                Подробнее
              </button>
              <button
                type="button"
                className={`btn btn-sm ${u.is_banned ? 'btn-success' : 'btn-danger'}`}
                disabled={busy === u.id}
                onClick={() => toggleBan(u)}
              >
                {u.is_banned ? 'Разбанить' : 'Забанить'}
              </button>
            </div>
          </div>
        ))}
    </div>
  )
}
