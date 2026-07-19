import { useEffect, useState } from 'react'
import { api, formatName, mediaHeaders, mediaUrl, shortDate, type VerificationItem } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/Shell'

interface Props {
  toast: (msg: string, type?: 'success' | 'error') => void
}

function MediaPreview({ fileId }: { fileId: string }) {
  const [src, setSrc] = useState<string | null>(null)
  const [kind, setKind] = useState<'video' | 'image'>('video')
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let revoked: string | null = null
    let cancelled = false

    async function load() {
      try {
        const res = await fetch(mediaUrl(fileId), { headers: mediaHeaders() })
        if (!res.ok) throw new Error('fail')
        const type = res.headers.get('content-type') || ''
        const blob = await res.blob()
        if (cancelled) return
        const url = URL.createObjectURL(blob)
        revoked = url
        setSrc(url)
        setKind(type.startsWith('image/') ? 'image' : 'video')
      } catch {
        if (!cancelled) setFailed(true)
      }
    }

    load()
    return () => {
      cancelled = true
      if (revoked) URL.revokeObjectURL(revoked)
    }
  }, [fileId])

  if (failed) return <p className="row-meta">Медиа недоступно</p>
  if (!src) return <div className="spinner" style={{ margin: '12px auto' }} />
  if (kind === 'image') return <img className="media-preview" src={src} alt="Верификация" />
  return <video className="media-preview" src={src} controls playsInline />
}

export function Verifications({ toast }: Props) {
  const [items, setItems] = useState<VerificationItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState<number | null>(null)

  async function load() {
    setLoading(true)
    setError('')
    try {
      setItems(await api<VerificationItem[]>('/admin/verifications'))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function act(id: number, action: 'approve' | 'reject') {
    if (action === 'reject' && !confirm('Отклонить верификацию?')) return
    setBusy(id)
    try {
      await api(`/admin/verifications/${id}/${action}`, { method: 'PATCH' })
      toast(action === 'approve' ? 'Верификация одобрена' : 'Верификация отклонена')
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
      <h2 className="section-title">Верификации</h2>
      <p className="section-desc">Ручная проверка заявок</p>

      {items.length === 0 && <EmptyState title="Нет заявок" desc="Очередь пуста" />}

      {items.map((v) => (
        <div key={v.id} className="card row-card">
          <div className="row-top">
            <div>
              <div className="row-title">{formatName(v.user)}</div>
              <div className="row-meta">{shortDate(v.created_at)}</div>
            </div>
            <span className="badge">На проверке</span>
          </div>
          <div className="row-meta">
            Код: <span className="hl mono">{v.code}</span>
            {v.gesture ? <> · Жест: {v.gesture}</> : null}
          </div>
          {v.video_file_id && <MediaPreview fileId={v.video_file_id} />}
          <div className="row-actions">
            <button type="button" className="btn btn-sm btn-success" disabled={busy === v.id} onClick={() => act(v.id, 'approve')}>
              Одобрить
            </button>
            <button type="button" className="btn btn-sm btn-danger" disabled={busy === v.id} onClick={() => act(v.id, 'reject')}>
              Отклонить
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
