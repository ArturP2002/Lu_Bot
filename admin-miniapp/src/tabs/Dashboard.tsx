import { useEffect, useState } from 'react'
import { api, type Stats } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/Shell'

interface Props {
  onError?: (msg: string) => void
}

export function Dashboard({ onError }: Props) {
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    setError('')
    try {
      setStats(await api<Stats>('/admin/stats'))
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(msg)
      onError?.(msg)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} onRetry={load} />
  if (!stats) return <EmptyState title="Нет данных" />

  const cards = [
    { label: 'Пользователи', value: stats.users },
    { label: 'Активные 7д', value: stats.active_users_7d ?? 0 },
    { label: 'Premium', value: stats.premium_users ?? 0 },
    { label: 'Тусовки', value: stats.events },
    { label: 'Жалобы', value: stats.pending_complaints, alert: stats.pending_complaints > 0 },
    { label: 'Верификации', value: stats.pending_verifications, alert: stats.pending_verifications > 0 },
    { label: 'Выводы', value: stats.pending_withdraws, alert: stats.pending_withdraws > 0 },
    { label: 'Платежи ⚡', value: stats.payments_sparks ?? 0 },
    { label: 'Доход ₽', value: Math.round(stats.revenue_estimate ?? stats.payments_rub ?? 0) },
    { label: 'Искры +', value: stats.sparks_in ?? 0 },
    { label: 'Искры −', value: stats.sparks_out ?? 0 },
  ]

  return (
    <div>
      <h2 className="section-title">Обзор</h2>
      <p className="section-desc">Ключевые метрики и очереди модерации</p>
      <div className="stats-grid">
        {cards.map((c) => (
          <div key={c.label} className={`stat-card${c.alert ? ' alert' : ''}`}>
            <div className="stat-label">{c.label}</div>
            <div className="stat-value mono">{c.value}</div>
          </div>
        ))}
      </div>
    </div>
  )
}