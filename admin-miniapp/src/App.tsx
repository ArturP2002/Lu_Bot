import { useCallback, useEffect, useState } from 'react'
import type { TabId } from './api'
import { Shell } from './components/Shell'
import { Bloggers } from './tabs/Bloggers'
import { Broadcasts } from './tabs/Broadcasts'
import { Complaints } from './tabs/Complaints'
import { Dashboard } from './tabs/Dashboard'
import { Events } from './tabs/Events'
import { Payments } from './tabs/Payments'
import { Premium } from './tabs/Premium'
import { Referrals } from './tabs/Referrals'
import { Settings } from './tabs/Settings'
import { Sparks } from './tabs/Sparks'
import { Users } from './tabs/Users'
import { Verifications } from './tabs/Verifications'
import { Withdraws } from './tabs/Withdraws'

export default function App() {
  const [tab, setTab] = useState<TabId>('dashboard')
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)

  useEffect(() => {
    window.Telegram?.WebApp?.ready()
    window.Telegram?.WebApp?.expand()
  }, [])

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 2800)
    return () => clearTimeout(t)
  }, [toast])

  const showToast = useCallback((message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type })
    try {
      window.Telegram?.WebApp?.HapticFeedback?.impactOccurred(type === 'error' ? 'heavy' : 'light')
    } catch {
      /* ignore */
    }
  }, [])

  return (
    <Shell tab={tab} onTab={setTab} toast={toast}>
      {tab === 'dashboard' && <Dashboard onError={(m) => showToast(m, 'error')} />}
      {tab === 'users' && <Users toast={showToast} />}
      {tab === 'complaints' && <Complaints toast={showToast} />}
      {tab === 'verifications' && <Verifications toast={showToast} />}
      {tab === 'events' && <Events toast={showToast} />}
      {tab === 'premium' && <Premium toast={showToast} />}
      {tab === 'sparks' && <Sparks toast={showToast} />}
      {tab === 'referrals' && <Referrals toast={showToast} />}
      {tab === 'bloggers' && <Bloggers toast={showToast} />}
      {tab === 'broadcasts' && <Broadcasts toast={showToast} />}
      {tab === 'payments' && <Payments toast={showToast} />}
      {tab === 'withdraws' && <Withdraws toast={showToast} />}
      {tab === 'settings' && <Settings toast={showToast} />}
    </Shell>
  )
}
