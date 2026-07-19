import { useEffect, useMemo, useState } from 'react'
import { api, shortDate } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/Shell'
import { label, REFERRAL_REWARD, REFERRAL_TRACK } from '../labels'

interface RefRow {
  id: number
  display_name: string | null
  username: string | null
  telegram_id: number
  referral_code: string | null
  referral_count: number
  referral_track: string | null
  rewards: { threshold: number; reward_type: string; claimed_at: string | null }[]
}

type TrackFilter = 'all' | 'standard' | 'blogger'

interface Props {
  toast: (message: string, type?: 'success' | 'error') => void
}

const TRACK_FILTERS: { value: TrackFilter; label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'standard', label: 'Обычная' },
  { value: 'blogger', label: 'Блогер' },
]

function peopleLabel(n: number): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return `${n} человек`
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${n} человека`
  return `${n} человек`
}

export function Referrals({ toast }: Props) {
  const [items, setItems] = useState<RefRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [track, setTrack] = useState<TrackFilter>('all')

  async function load() {
    setLoading(true)
    setError('')
    try {
      setItems(await api<RefRow[]>('/admin/referrals'))
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(msg)
      toast(msg, 'error')
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
      if (track !== 'all' && (u.referral_track || 'standard') !== track) return false
      if (!q) return true
      const hay = [
        String(u.id),
        String(u.telegram_id),
        u.display_name || '',
        u.username || '',
        u.referral_code || '',
        label(REFERRAL_TRACK, u.referral_track),
      ]
        .join(' ')
        .toLowerCase()
      return hay.includes(q)
    })
  }, [items, query, track])

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} onRetry={load} />

  const totalInvites = items.reduce((sum, u) => sum + (u.referral_count || 0), 0)

  return (
    <div>
      <h2 className="section-title">Рефералы</h2>
      <p className="section-desc">
        Начисления и пороги · {items.length} участников · {totalInvites} приглашённых
      </p>

      <div className="search-bar">
        <input
          className="input"
          placeholder="Поиск: имя, @username, код или ID"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div className="field">
        <label>Программа</label>
        <div className="chips">
          {TRACK_FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              className={`chip${track === f.value ? ' active' : ''}`}
              onClick={() => setTrack(f.value)}
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
          title={items.length ? 'Ничего не найдено' : 'Пока нет реферальной активности'}
          desc={items.length ? 'Измените поиск или фильтр' : undefined}
        />
      ) : (
        filtered.map((u) => (
          <div key={u.id} className="card row-card">
            <div className="row-top">
              <div>
                <div className="row-title">{u.display_name || u.username || `Пользователь #${u.id}`}</div>
                <div className="row-meta">
                  #{u.id}
                  {u.username ? ` · @${u.username}` : ''}
                  {` · tg ${u.telegram_id}`}
                </div>
              </div>
              <div className="badges">
                <span className="badge">{label(REFERRAL_TRACK, u.referral_track, 'Обычная')}</span>
              </div>
            </div>

            <div className="detail-row">
              <span className="detail-label">Приглашено</span>
              <span className="detail-value">{peopleLabel(u.referral_count)}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Реф. код</span>
              <span className="detail-value mono">{u.referral_code || '—'}</span>
            </div>

            {u.rewards.length > 0 && (
              <div>
                <div className="detail-label" style={{ marginBottom: 4 }}>
                  Полученные награды
                </div>
                <div className="reward-list">
                  {u.rewards.map((r) => (
                    <div key={`${u.id}-${r.threshold}-${r.reward_type}`} className="reward-item">
                      <span>
                        Порог {r.threshold}: {label(REFERRAL_REWARD, r.reward_type)}
                      </span>
                      <span className="muted mono">{shortDate(r.claimed_at) || '—'}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {!u.rewards.length && (
              <div className="row-meta">Награды ещё не получены</div>
            )}
          </div>
        ))
      )}
    </div>
  )
}
