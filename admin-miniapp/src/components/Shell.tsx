import type { ReactNode } from 'react'
import type { TabId } from '../api'

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: 'dashboard', label: 'Обзор', icon: '◈' },
  { id: 'users', label: 'Люди', icon: '◎' },
  { id: 'complaints', label: 'Жалобы', icon: '⚑' },
  { id: 'verifications', label: 'Вериф.', icon: '✓' },
  { id: 'events', label: 'Тусовки', icon: '✧' },
  { id: 'premium', label: 'Premium', icon: '★' },
  { id: 'sparks', label: 'Искры', icon: '⚡' },
  { id: 'referrals', label: 'Рефералы', icon: '↗' },
  { id: 'bloggers', label: 'Блогеры', icon: '◉' },
  { id: 'broadcasts', label: 'Рассылки', icon: '✉' },
  { id: 'payments', label: 'Платежи', icon: '◇' },
  { id: 'withdraws', label: 'Выводы', icon: '⬡' },
  { id: 'settings', label: 'Настройки', icon: '⚙' },
]

interface ShellProps {
  tab: TabId
  onTab: (t: TabId) => void
  toast: { message: string; type: 'success' | 'error' } | null
  children: ReactNode
}

export function Shell({ tab, onTab, toast, children }: ShellProps) {
  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="brand-name">LUMA</span>
          <span className="brand-sub">Admin</span>
        </div>
        <nav className="tabs" aria-label="Разделы">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`tab${tab === t.id ? ' active' : ''}`}
              onClick={() => onTab(t.id)}
            >
              <span className="tab-icon">{t.icon}</span>
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main className="content" key={tab}>
        {children}
      </main>
      {toast && (
        <div className={`toast ${toast.type}`} role="status">
          {toast.message}
        </div>
      )}
    </div>
  )
}

export function LoadingState({ label = 'Загрузка…' }: { label?: string }) {
  return (
    <div className="state-box">
      <div className="spinner" />
      <p>{label}</p>
    </div>
  )
}

export function EmptyState({ title, desc }: { title: string; desc?: string }) {
  return (
    <div className="state-box">
      <p className="state-title">{title}</p>
      {desc && <p>{desc}</p>}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state-box error">
      <p className="state-title">Что-то не так</p>
      <p>{message}</p>
      {onRetry && (
        <button type="button" className="btn btn-ghost btn-sm" style={{ marginTop: 14 }} onClick={onRetry}>
          Повторить
        </button>
      )}
    </div>
  )
}
