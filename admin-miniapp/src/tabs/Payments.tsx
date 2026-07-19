import { useEffect, useState } from 'react'
import { api, formatName, shortDate, type PaymentItem } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/Shell'
import { label, PAYMENT_PROVIDER, PAYMENT_PURPOSE, PAYMENT_STATUS } from '../labels'

interface Props {
  toast: (msg: string, type?: 'success' | 'error') => void
}

const PROVIDERS = [
  { value: '', label: 'Все' },
  { value: 'yookassa', label: 'ЮKassa' },
  { value: 'stars', label: 'Telegram Stars' },
]

const STATUSES = [
  { value: '', label: 'Все статусы' },
  { value: 'succeeded', label: 'Оплачен' },
  { value: 'pending', label: 'Ожидает' },
  { value: 'canceled', label: 'Отменён' },
]

export function Payments({ toast: _toast }: Props) {
  const [items, setItems] = useState<PaymentItem[]>([])
  const [provider, setProvider] = useState('')
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function load(p = provider, s = status) {
    setLoading(true)
    setError('')
    try {
      const qs = new URLSearchParams()
      if (p) qs.set('provider', p)
      if (s) qs.set('status', s)
      const q = qs.toString()
      setItems(await api<PaymentItem[]>(`/admin/payments${q ? `?${q}` : ''}`))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <div>
      <h2 className="section-title">Платежи</h2>
      <p className="section-desc">ЮKassa и Telegram Stars</p>

      <div className="field">
        <label>Провайдер</label>
        <div className="chips">
          {PROVIDERS.map((o) => (
            <button
              key={o.value || 'all'}
              type="button"
              className={`chip${provider === o.value ? ' active' : ''}`}
              onClick={() => {
                setProvider(o.value)
                load(o.value, status)
              }}
            >
              {o.label}
            </button>
          ))}
        </div>
      </div>
      <div className="field">
        <label>Статус</label>
        <div className="chips">
          {STATUSES.map((o) => (
            <button
              key={o.value || 'all-status'}
              type="button"
              className={`chip${status === o.value ? ' active' : ''}`}
              onClick={() => {
                setStatus(o.value)
                load(provider, o.value)
              }}
            >
              {o.label}
            </button>
          ))}
        </div>
      </div>

      {loading && <LoadingState />}
      {!loading && error && <ErrorState message={error} onRetry={() => load()} />}
      {!loading && !error && items.length === 0 && <EmptyState title="Платежей нет" />}

      {!loading &&
        !error &&
        items.map((p) => (
          <div key={p.id} className="card row-card">
            <div className="row-top">
              <div>
                <div className="row-title">{formatName(p.user)}</div>
                <div className="row-meta">
                  {shortDate(p.paid_at || p.created_at)} · #{p.id}
                  {p.is_stub ? ' · демо' : ''}
                </div>
              </div>
              <div className="badges">
                <span className="badge">{label(PAYMENT_PROVIDER, p.provider)}</span>
                <span
                  className={`badge ${
                    p.status === 'succeeded' ? 'success' : p.status === 'canceled' ? 'danger' : 'warning'
                  }`}
                >
                  {label(PAYMENT_STATUS, p.status)}
                </span>
              </div>
            </div>
            <div className="row-meta mono">
              <span className="hl">{p.amount_sparks}</span> искр
              {p.provider === 'yookassa' ? ` · ${p.amount_rub} ₽` : ''}
              {p.purpose ? ` · ${label(PAYMENT_PURPOSE, p.purpose)}` : ''}
            </div>
            {p.external_id && <div className="row-meta">ID: {p.external_id}</div>}
          </div>
        ))}
    </div>
  )
}
