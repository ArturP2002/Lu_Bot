declare global {
  interface Window {
    Telegram?: {
      WebApp: {
        initData: string
        ready: () => void
        expand: () => void
        HapticFeedback?: { impactOccurred: (style: string) => void }
      }
    }
  }
}

const API = import.meta.env.VITE_API_URL || '/api'

export type TabId =
  | 'dashboard'
  | 'users'
  | 'complaints'
  | 'verifications'
  | 'events'
  | 'broadcasts'
  | 'payments'
  | 'withdraws'
  | 'premium'
  | 'sparks'
  | 'referrals'
  | 'bloggers'
  | 'settings'

export interface UserBrief {
  id: number
  telegram_id: number
  display_name: string | null
  username: string | null
  city: string | null
}

export interface Stats {
  users: number
  events: number
  pending_complaints: number
  pending_verifications: number
  pending_withdraws: number
  premium_users?: number
  payments_sparks?: number
  payments_rub?: number
  active_users_7d?: number
  sparks_in?: number
  sparks_out?: number
  revenue_estimate?: number
}

export interface AdminUser {
  id: number
  telegram_id: number
  username: string | null
  display_name: string | null
  city: string | null
  age: number | null
  verified: boolean
  premium: boolean
  premium_until?: string | null
  disabled: boolean
  is_banned: boolean
  warning_count: number
  sparks_balance: number
  created_at: string | null
}

export interface UserDetail extends AdminUser {
  country: string | null
  gender: string | null
  seeking: string | null
  visible_to: string | null
  bio: string | null
  contact_phone: string | null
  photo_file_id: string | null
  profile_completed: boolean
  rating_avg: number
  rating_count: number
  events_attended: number
  events_organized: number
  referral_code: string | null
  referral_track: string | null
  referral_count: number
  goal: { title: string; target_sparks: number; collected_sparks: number } | null
  updated_at: string | null
  recent_transactions: { id: number; amount: number; tx_type: string; created_at: string | null }[]
  recent_payments: {
    id: number
    provider: string
    amount_sparks: number
    amount_rub: number
    status: string
    created_at: string | null
  }[]
}

export interface ComplaintItem {
  id: number
  type: string
  text: string
  target_user_id: number | null
  target_user: UserBrief | null
  reporter: UserBrief | null
  event_id: number | null
  event_title: string | null
  created_at: string | null
}

export interface VerificationItem {
  id: number
  user_id: number
  user: UserBrief | null
  code: string
  gesture: string
  video_file_id: string | null
  created_at: string | null
}

export interface EventItem {
  id: number
  title: string
  status: string
  city: string
  address: string
  event_date: string
  event_time: string
  price: number
  men_needed: number
  women_needed: number
  men_count: number
  women_count: number
  category: string | null
  description: string | null
  photo_file_id: string | null
  organizer: UserBrief | null
  created_at: string | null
}

export interface BroadcastFilters {
  gender?: string | null
  premium?: string | null
}

export interface BroadcastItem {
  id: number
  message_text: string
  status: string
  sent_count: number
  total_count: number
  filters?: BroadcastFilters | null
  created_at: string | null
}

export interface WithdrawItem {
  id: number
  user_id: number
  user: UserBrief | null
  amount: number
  fee: number
  net_amount: number
  requisites: string | null
  status: string
  created_at: string | null
}

export interface PaymentItem {
  id: number
  user_id: number
  user: UserBrief | null
  provider: string
  external_id: string | null
  amount_sparks: number
  amount_rub: number
  status: string
  purpose: string
  is_stub: boolean
  created_at: string | null
  paid_at: string | null
}

export interface SettingMeta {
  key: string
  label: string
  hint: string
  type: string
  group: string
}

export interface SettingsResponse {
  values: Record<string, string>
  meta: SettingMeta[]
  defaults: Record<string, string>
}

function apiHeaders(): HeadersInit {
  const initData = window.Telegram?.WebApp?.initData || ''
  return {
    'X-Telegram-Init-Data': initData,
    'Content-Type': 'application/json',
  }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...apiHeaders(),
      ...(options?.headers || {}),
    },
  })
  if (!res.ok) {
    let msg = `Ошибка ${res.status}`
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') msg = body.detail
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, msg)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export function mediaUrl(fileId: string): string {
  return `${API}/admin/media/${encodeURIComponent(fileId)}`
}

export function mediaHeaders(): HeadersInit {
  return { 'X-Telegram-Init-Data': window.Telegram?.WebApp?.initData || '' }
}

export function formatName(u: UserBrief | null | undefined, fallback = '—'): string {
  if (!u) return fallback
  return u.display_name || (u.username ? `@${u.username}` : `ID ${u.telegram_id}`)
}

export function shortDate(value: string | null | undefined): string {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('ru-RU', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}
