/** Русские подписи для статусов и кодов в админке. */

export const PAYMENT_STATUS: Record<string, string> = {
  pending: 'Ожидает',
  succeeded: 'Оплачен',
  canceled: 'Отменён',
}

export const PAYMENT_PROVIDER: Record<string, string> = {
  yookassa: 'ЮKassa',
  stars: 'Telegram Stars',
}

export const PAYMENT_PURPOSE: Record<string, string> = {
  buy_sparks: 'Покупка искр',
  premium: 'Premium',
}

export const VERIFICATION_STATUS: Record<string, string> = {
  pending: 'На проверке',
  approved: 'Одобрена',
  rejected: 'Отклонена',
}

export const REFERRAL_TRACK: Record<string, string> = {
  standard: 'Обычная',
  blogger: 'Блогер',
}

export const REFERRAL_REWARD: Record<string, string> = {
  premium_1m: 'Premium на 1 мес.',
  premium_3m: 'Premium на 3 мес.',
  sparks_200: '200 искр',
  sparks_300_premium_6m: '300 искр + Premium на 6 мес.',
  sparks_1000_premium_forever: '1000 искр + Premium навсегда',
}

export const BLOGGER_STATUS: Record<string, string> = {
  pending: 'На проверке',
  approved: 'Одобрен',
  rejected: 'Отклонён',
}

export const BROADCAST_STATUS: Record<string, string> = {
  pending: 'В очереди',
  running: 'Отправляется',
  completed: 'Завершена',
  failed: 'Ошибка',
}

export const WITHDRAW_STATUS: Record<string, string> = {
  pending: 'Ожидает',
  processing: 'В обработке',
  completed: 'Выполнен',
  rejected: 'Отклонён',
}

export const EVENT_STATUS: Record<string, string> = {
  active: 'Активна',
  closed: 'Закрыта',
  deleted: 'Удалена',
}

export const TX_TYPE: Record<string, string> = {
  purchase: 'Покупка искр',
  buy_sparks: 'Покупка искр',
  premium: 'Premium',
  withdraw: 'Вывод средств',
  withdraw_fee: 'Комиссия за вывод',
  withdraw_refund: 'Возврат вывода',
  support_sent: 'Поддержка отправлена',
  support_received: 'Поддержка получена',
  rating_reset: 'Сброс рейтинга',
  goal_to_balance: 'С цели на баланс',
  referral: 'Реферал',
  referral_reward: 'Реферальная награда',
  admin_adjust: 'Корректировка админом',
  event_fee: 'Взнос за тусовку',
  event_fee_received: 'Получен взнос за тусовку',
  event_boost: 'Буст тусовки',
  event_pin: 'Закреп тусовки',
  blogger_commission: 'Комиссия блогера',
  blogger_views_500k: 'Награда за 500 тыс. просмотров',
  blogger_views_1m: 'Награда за 1 млн просмотров',
}

export const COMPLAINT_TYPE: Record<string, string> = {
  user: 'На пользователя',
  event: 'На тусовку',
  profile: 'На анкету',
}

export function label(map: Record<string, string>, key: string | null | undefined, fallback?: string): string {
  if (!key) return fallback || '—'
  return map[key] || fallback || key
}
