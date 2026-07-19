import { useEffect, useState } from 'react'
import { api, shortDate, type BroadcastItem } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/Shell'
import { BROADCAST_STATUS, label } from '../labels'

interface Props {
  toast: (msg: string, type?: 'success' | 'error') => void
}

const STATUS_CLASS: Record<string, string> = {
  pending: 'warning',
  running: 'warning',
  completed: 'success',
  failed: 'danger',
}

const GENDER_OPTS = [
  { value: 'all', label: 'Все' },
  { value: 'male', label: 'Мужчины' },
  { value: 'female', label: 'Женщины' },
  { value: 'other', label: 'Другое' },
]

const PREMIUM_OPTS = [
  { value: 'all', label: 'Все' },
  { value: 'premium', label: 'Premium' },
  { value: 'free', label: 'Без Premium' },
]

function filtersLabel(f?: { gender?: string | null; premium?: string | null } | null): string {
  if (!f) return 'Всем'
  const parts: string[] = []
  if (f.gender && f.gender !== 'all') {
    parts.push(GENDER_OPTS.find((o) => o.value === f.gender)?.label || f.gender)
  }
  if (f.premium && f.premium !== 'all') {
    parts.push(PREMIUM_OPTS.find((o) => o.value === f.premium)?.label || f.premium)
  }
  return parts.length ? parts.join(' · ') : 'Всем'
}

export function Broadcasts({ toast }: Props) {
  const [text, setText] = useState('')
  const [gender, setGender] = useState('all')
  const [premium, setPremium] = useState('all')
  const [items, setItems] = useState<BroadcastItem[]>([])
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    setError('')
    try {
      setItems(await api<BroadcastItem[]>('/admin/broadcasts'))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function send() {
    if (!text.trim()) {
      toast('Введите текст рассылки', 'error')
      return
    }
    const audience = filtersLabel({ gender, premium })
    if (!confirm(`Отправить рассылку: ${audience}?`)) return
    setSending(true)
    try {
      await api('/admin/broadcasts', {
        method: 'POST',
        body: JSON.stringify({
          message_text: text.trim(),
          filters: { gender, premium },
        }),
      })
      setText('')
      toast('Рассылка запущена')
      await load()
      // статус обновится после фоновой отправки
      setTimeout(() => load(), 2500)
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), 'error')
    } finally {
      setSending(false)
    }
  }

  async function sendNow(id: number) {
    if (!confirm('Запустить отправку этой рассылки сейчас?')) return
    setBusyId(id)
    try {
      await api(`/admin/broadcasts/${id}/send`, { method: 'POST' })
      toast('Отправка запущена')
      await load()
      setTimeout(() => load(), 2500)
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), 'error')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div>
      <h2 className="section-title">Рассылки</h2>
      <p className="section-desc">Сегментированные массовые сообщения</p>

      <div className="card">
        <div className="field">
          <label>Аудитория по полу</label>
          <div className="chips">
            {GENDER_OPTS.map((o) => (
              <button
                key={o.value}
                type="button"
                className={`chip${gender === o.value ? ' active' : ''}`}
                onClick={() => setGender(o.value)}
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>
        <div className="field">
          <label>Premium</label>
          <div className="chips">
            {PREMIUM_OPTS.map((o) => (
              <button
                key={o.value}
                type="button"
                className={`chip${premium === o.value ? ' active' : ''}`}
                onClick={() => setPremium(o.value)}
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>
        <div className="field">
          <label htmlFor="broadcast">Текст сообщения</label>
          <textarea
            id="broadcast"
            className="textarea"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Поддерживается HTML (как в боте)"
          />
        </div>
        <button type="button" className="btn btn-primary btn-block" disabled={sending} onClick={send}>
          {sending ? 'Отправка…' : `Отправить · ${filtersLabel({ gender, premium })}`}
        </button>
      </div>

      <div className="divider" />
      <p className="section-desc" style={{ marginBottom: 12 }}>
        История
      </p>

      {loading && <LoadingState />}
      {!loading && error && <ErrorState message={error} onRetry={load} />}
      {!loading && !error && items.length === 0 && <EmptyState title="Пока нет рассылок" />}

      {!loading &&
        !error &&
        items.map((b) => (
          <div key={b.id} className="card row-card">
            <div className="row-top">
              <div className="row-meta">{shortDate(b.created_at)} · #{b.id}</div>
              <span className={`badge ${STATUS_CLASS[b.status] || 'muted'}`}>
                {label(BROADCAST_STATUS, b.status)}
              </span>
            </div>
            <div className="row-meta">{filtersLabel(b.filters)}</div>
            <div className="row-body">{b.message_text}</div>
            <div className="row-meta mono">
              Доставлено: {b.sent_count}/{b.total_count || '—'}
            </div>
            {(b.status === 'pending' || b.status === 'failed' || b.status === 'completed') && (
              <div className="row-actions">
                <button
                  type="button"
                  className="btn btn-sm btn-primary"
                  disabled={busyId === b.id}
                  onClick={() => sendNow(b.id)}
                >
                  {b.status === 'completed' ? 'Отправить снова' : 'Отправить сейчас'}
                </button>
              </div>
            )}
          </div>
        ))}
    </div>
  )
}
