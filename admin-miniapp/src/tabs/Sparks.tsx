import { useEffect, useMemo, useState } from 'react'
import { api, formatName, shortDate } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/Shell'
import { label, TX_TYPE } from '../labels'

interface Tx {
  id: number
  user_id: number
  user: { id: number; telegram_id: number; display_name: string | null; username: string | null; city: string | null } | null
  amount: number
  tx_type: string
  reference_id: number | null
  created_at: string | null
}

interface Props {
  toast: (message: string, type?: 'success' | 'error') => void
}

const TYPE_FILTERS: { value: string; label: string }[] = [
  { value: '', label: 'Все' },
  { value: 'purchase', label: 'Покупка' },
  { value: 'event_fee', label: 'Взнос' },
  { value: 'event_fee_received', label: 'Взнос получен' },
  { value: 'withdraw', label: 'Вывод' },
  { value: 'withdraw_fee', label: 'Комиссия' },
  { value: 'withdraw_refund', label: 'Возврат' },
  { value: 'admin_adjust', label: 'Корректировка' },
  { value: 'referral_reward', label: 'Реферал' },
  { value: 'blogger_commission', label: 'Блогер' },
]

function amountClass(amount: number): string {
  if (amount > 0) return 'amount-pos'
  if (amount < 0) return 'amount-neg'
  return 'amount-zero'
}

function formatAmount(amount: number): string {
  return `${amount > 0 ? '+' : ''}${amount}`
}

export function Sparks({ toast }: Props) {
  const [items, setItems] = useState<Tx[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [userId, setUserId] = useState('')
  const [amount, setAmount] = useState('')
  const [query, setQuery] = useState('')
  const [txType, setTxType] = useState('')
  const [direction, setDirection] = useState<'all' | 'in' | 'out'>('all')
  const [busy, setBusy] = useState(false)

  async function load(type = txType) {
    setLoading(true)
    setError('')
    try {
      const qs = type ? `?tx_type=${encodeURIComponent(type)}` : ''
      setItems(await api<Tx[]>(`/admin/sparks${qs}`))
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
    return items.filter((tx) => {
      if (direction === 'in' && tx.amount <= 0) return false
      if (direction === 'out' && tx.amount >= 0) return false
      if (!q) return true
      const hay = [
        String(tx.id),
        String(tx.user_id),
        String(tx.user?.telegram_id || ''),
        tx.user?.display_name || '',
        tx.user?.username || '',
        label(TX_TYPE, tx.tx_type),
        tx.tx_type,
      ]
        .join(' ')
        .toLowerCase()
      return hay.includes(q)
    })
  }, [items, query, direction])

  async function adjust() {
    if (!userId.trim() || !amount.trim()) {
      toast('Укажите ID и сумму', 'error')
      return
    }
    setBusy(true)
    try {
      await api('/admin/sparks/adjust', {
        method: 'POST',
        body: JSON.stringify({ telegram_id: Number(userId), amount: Number(amount) }),
      })
      toast('Баланс обновлён')
      setUserId('')
      setAmount('')
      await load()
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <h2 className="section-title">Искры</h2>
      <p className="section-desc">Журнал операций и ручная корректировка</p>

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
              <label>Сумма (+/−)</label>
              <input
                className="input"
                inputMode="numeric"
                placeholder="Например: 100 или −50"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </div>
          </div>
          <p className="form-hint">Положительное число — начислить, отрицательное — списать с баланса.</p>
          <button type="button" className="btn btn-primary btn-block" disabled={busy} onClick={adjust}>
            {busy ? 'Сохранение…' : 'Начислить / списать'}
          </button>
        </div>
      </div>

      <div className="search-bar">
        <input
          className="input"
          placeholder="Поиск: имя, @username, ID операции или пользователя"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div className="field">
        <label>Тип операции</label>
        <div className="chips">
          {TYPE_FILTERS.map((f) => (
            <button
              key={f.value || 'all'}
              type="button"
              className={`chip${txType === f.value ? ' active' : ''}`}
              onClick={() => {
                setTxType(f.value)
                load(f.value)
              }}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="field">
        <label>Направление</label>
        <div className="chips">
          {(
            [
              { value: 'all', label: 'Все' },
              { value: 'in', label: 'Приход' },
              { value: 'out', label: 'Расход' },
            ] as const
          ).map((f) => (
            <button
              key={f.value}
              type="button"
              className={`chip${direction === f.value ? ' active' : ''}`}
              onClick={() => setDirection(f.value)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {loading && <LoadingState />}
      {!loading && error && <ErrorState message={error} onRetry={() => load()} />}
      {!loading && !error && (
        <>
          <p className="toolbar-count">
            Показано {filtered.length}
            {filtered.length !== items.length ? ` из ${items.length}` : ''}
          </p>
          {!filtered.length ? (
            <EmptyState
              title={items.length ? 'Ничего не найдено' : 'Нет транзакций'}
              desc={items.length ? 'Измените поиск или фильтр' : undefined}
            />
          ) : (
            filtered.map((tx) => (
              <div key={tx.id} className="card row-card">
                <div className="row-top">
                  <div>
                    <div className="row-title">{label(TX_TYPE, tx.tx_type)}</div>
                    <div className="row-meta">
                      {formatName(tx.user)} · #{tx.user_id}
                      {tx.user?.username ? ` · @${tx.user.username}` : ''}
                    </div>
                  </div>
                  <div className={amountClass(tx.amount)}>
                    {formatAmount(tx.amount)} ⚡
                  </div>
                </div>
                <div className="row-meta mono">
                  {shortDate(tx.created_at)} · операция #{tx.id}
                  {tx.reference_id != null ? ` · ссылка #${tx.reference_id}` : ''}
                </div>
              </div>
            ))
          )}
        </>
      )}
    </div>
  )
}
