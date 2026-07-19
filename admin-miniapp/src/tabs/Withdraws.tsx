import { useEffect, useState } from 'react'
import { api, formatName, shortDate, type WithdrawItem } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/Shell'

interface Props {
  toast: (msg: string, type?: 'success' | 'error') => void
}

export function Withdraws({ toast }: Props) {
  const [items, setItems] = useState<WithdrawItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState<number | null>(null)

  async function load() {
    setLoading(true)
    setError('')
    try {
      setItems(await api<WithdrawItem[]>('/admin/withdraws?status=pending'))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function decide(id: number, decision: 'completed' | 'rejected') {
    const msg =
      decision === 'completed'
        ? 'Отметить вывод как выполненный?'
        : 'Отклонить заявку и вернуть искры пользователю?'
    if (!confirm(msg)) return
    setBusy(id)
    try {
      await api(`/admin/withdraws/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ decision }),
      })
      toast(decision === 'completed' ? 'Вывод выполнен' : 'Заявка отклонена, искры возвращены')
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
      <h2 className="section-title">Выводы</h2>
      <p className="section-desc">Заявки на вывод Искр</p>

      {items.length === 0 && <EmptyState title="Нет заявок" desc="Очередь выводов пуста" />}

      {items.map((w) => (
        <div key={w.id} className="card row-card">
          <div className="row-top">
            <div>
              <div className="row-title">{formatName(w.user)}</div>
              <div className="row-meta">{shortDate(w.created_at)} · #{w.id}</div>
            </div>
            <span className="badge warning">Ожидает</span>
          </div>
          <div className="row-meta mono">
            Сумма: <span className="hl">{w.amount}</span> · Комиссия: {w.fee} · К выплате:{' '}
            <span className="hl">{w.net_amount}</span>
          </div>
          {w.requisites && (
            <div className="row-body">
              <strong>Реквизиты:</strong> {w.requisites}
            </div>
          )}
          <div className="row-actions">
            <button
              type="button"
              className="btn btn-sm btn-success"
              disabled={busy === w.id}
              onClick={() => decide(w.id, 'completed')}
            >
              Выполнено
            </button>
            <button
              type="button"
              className="btn btn-sm btn-danger"
              disabled={busy === w.id}
              onClick={() => decide(w.id, 'rejected')}
            >
              Отклонить
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
