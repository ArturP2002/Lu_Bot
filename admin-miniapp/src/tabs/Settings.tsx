import { useEffect, useState } from 'react'
import { api, type SettingMeta, type SettingsResponse } from '../api'
import { ErrorState, LoadingState } from '../components/Shell'

interface Props {
  toast: (msg: string, type?: 'success' | 'error') => void
}

const GROUP_LABELS: Record<string, string> = {
  pricing: 'Цены и курсы',
  fees: 'Комиссии',
  limits: 'Лимиты',
  feed: 'Фильтры ленты «Оценивать»',
  links: 'Ссылки',
  payments: 'Платежи',
}

const GROUP_ORDER = ['pricing', 'fees', 'limits', 'feed', 'links', 'payments']

function isTruthy(v: string | undefined): boolean {
  return ['1', 'true', 'yes', 'on', 'enabled'].includes((v || '').trim().toLowerCase())
}

export function Settings({ toast }: Props) {
  const [values, setValues] = useState<Record<string, string>>({})
  const [meta, setMeta] = useState<SettingMeta[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    setError('')
    try {
      const data = await api<SettingsResponse>('/admin/settings')
      setValues(data.values)
      setMeta(data.meta)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  function setField(key: string, value: string) {
    setValues((prev) => ({ ...prev, [key]: value }))
  }

  async function save() {
    for (const m of meta) {
      const v = values[m.key]
      if (m.type === 'bool') continue
      if (v === undefined || String(v).trim() === '') {
        toast(`Заполните: ${m.label}`, 'error')
        return
      }
      if (m.type === 'float' || m.type === 'int') {
        const n = Number(v)
        if (!Number.isFinite(n) || n < 0) {
          toast(`Некорректное значение: ${m.label}`, 'error')
          return
        }
      }
    }
    setSaving(true)
    try {
      const payload: Record<string, string> = {}
      for (const m of meta) {
        if (m.type === 'bool') {
          payload[m.key] = isTruthy(values[m.key]) ? '1' : '0'
        } else {
          payload[m.key] = String(values[m.key] ?? '').trim()
        }
      }
      await api('/admin/settings/bulk', {
        method: 'PUT',
        body: JSON.stringify({ values: payload }),
      })
      toast('Настройки сохранены')
      await load()
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), 'error')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} onRetry={load} />

  return (
    <div>
      <h2 className="section-title">Настройки</h2>
      <p className="section-desc">Экономика, лента и платежи. Пустые значения берутся из .env</p>

      {GROUP_ORDER.map((group) => {
        const fields = meta.filter((m) => m.group === group)
        if (!fields.length) return null
        return (
          <div key={group} className="card" style={{ marginBottom: 12 }}>
            <div className="detail-label" style={{ marginBottom: 14 }}>
              {GROUP_LABELS[group] || group}
            </div>
            {fields.map((m) => (
              <div className="field" key={m.key}>
                <label htmlFor={m.key}>{m.label}</label>
                {m.type === 'bool' ? (
                  <div className="chips">
                    <button
                      type="button"
                      className={`chip${isTruthy(values[m.key]) ? ' active' : ''}`}
                      onClick={() => setField(m.key, '1')}
                    >
                      {group === 'feed' ? 'Учитывать' : 'Вкл'}
                    </button>
                    <button
                      type="button"
                      className={`chip${!isTruthy(values[m.key]) ? ' active' : ''}`}
                      onClick={() => setField(m.key, '0')}
                    >
                      {group === 'feed' ? 'Не учитывать' : 'Выкл'}
                    </button>
                  </div>
                ) : (
                  <input
                    id={m.key}
                    className="input"
                    type={m.type === 'url' ? 'url' : 'number'}
                    min={m.type === 'url' ? undefined : 0}
                    step={m.type === 'float' ? '0.01' : m.type === 'int' ? '1' : undefined}
                    value={values[m.key] ?? ''}
                    onChange={(e) => setField(m.key, e.target.value)}
                    placeholder={m.type === 'url' ? 'https://…' : undefined}
                  />
                )}
                {m.hint ? (
                  <p className="row-meta" style={{ marginTop: 6 }}>
                    {m.hint}
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        )
      })}

      <button type="button" className="btn btn-primary btn-block" disabled={saving} onClick={save}>
        {saving ? 'Сохранение…' : 'Сохранить всё'}
      </button>
    </div>
  )
}
