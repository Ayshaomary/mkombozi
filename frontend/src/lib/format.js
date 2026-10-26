// Helpers to show money, numbers and dates in a friendly way.

const moneyFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const quantityFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })

// 12500 -> "TZS 12,500"
export function formatMoney(value) {
  return `TZS ${moneyFormat.format(Number(value) || 0)}`
}

// 12500 -> "12.5K", 2300000 -> "2.3M" (for chart axes and small tiles)
export function formatCompact(value) {
  const n = Number(value) || 0
  const abs = Math.abs(n)
  if (abs >= 1_000_000) return `${+(n / 1_000_000).toFixed(1)}M`
  if (abs >= 1_000) return `${+(n / 1_000).toFixed(1)}K`
  return String(Math.round(n))
}

// "3.00" -> "3", "1.50" -> "1.5"
export function formatQuantity(value) {
  return quantityFormat.format(Number(value) || 0)
}

function locale(lang) {
  return lang === 'sw' ? 'sw-TZ' : 'en-GB'
}

export function formatDate(value, lang) {
  if (!value) return ''
  const date = typeof value === 'string' && value.length === 10 ? new Date(`${value}T00:00:00`) : new Date(value)
  return date.toLocaleDateString(locale(lang), { day: 'numeric', month: 'short', year: 'numeric' })
}

export function formatDateTime(value, lang) {
  if (!value) return ''
  return new Date(value).toLocaleString(locale(lang), {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatWeekday(value, lang) {
  return new Date(`${value}T00:00:00`).toLocaleDateString(locale(lang), { weekday: 'short' })
}

// Today's date as YYYY-MM-DD in the user's local time
export function todayISO() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
