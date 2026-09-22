/* Locale-aware formatting helpers (TR / EN) */

const localeFor = (lang) => (lang === 'en' ? 'en-US' : 'tr-TR')

export function formatCurrency(value, lang = 'tr', { compact = false, decimals } = {}) {
  const opts = {
    style: 'currency',
    currency: 'TRY',
    maximumFractionDigits: decimals ?? (compact ? 1 : 0),
    minimumFractionDigits: decimals ?? 0,
  }
  if (compact) opts.notation = 'compact'
  try {
    return new Intl.NumberFormat(localeFor(lang), opts).format(value)
  } catch {
    return `₺${value}`
  }
}

export function formatNumber(value, lang = 'tr', { compact = false, decimals = 0 } = {}) {
  const opts = { maximumFractionDigits: decimals, minimumFractionDigits: 0 }
  if (compact) opts.notation = 'compact'
  return new Intl.NumberFormat(localeFor(lang), opts).format(value)
}

export function formatPercent(value, lang = 'tr', decimals = 1) {
  return new Intl.NumberFormat(localeFor(lang), {
    style: 'percent',
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  }).format(value / 100)
}

export function formatDate(date, lang = 'tr') {
  const d = typeof date === 'string' ? new Date(date) : date
  return new Intl.DateTimeFormat(localeFor(lang), {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(d)
}

// Month labels for charts
export const MONTHS = {
  tr: ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'],
  en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
}

export const WEEKDAYS = {
  tr: ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'],
  en: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
}
