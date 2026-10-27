import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useLanguage } from '../i18n/LanguageContext'
import { api } from '../lib/api'
import { formatDate, formatDateTime, formatMoney, formatQuantity } from '../lib/format'
import Icon from './Icon'

const REFRESH_EVERY_MS = 2 * 60 * 1000
const NotificationsContext = createContext(null)

// Loads notifications for the bell. Opening the list on the server also runs the automatic tasks.
export function NotificationsProvider({ children }) {
  const [items, setItems] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const location = useLocation()

  const refresh = useCallback(async () => {
    try {
      const data = await api.get('/notifications/')
      setItems(data.results)
      setUnreadCount(data.unread_count)
    } catch {
      // Not important enough to show an error; we try again soon
    }
  }, [])

  // Check when the app opens, on every page change, and every 2 minutes
  useEffect(() => {
    refresh()
  }, [refresh, location.pathname])

  useEffect(() => {
    const timer = setInterval(refresh, REFRESH_EVERY_MS)
    return () => clearInterval(timer)
  }, [refresh])

  const markRead = async (notification) => {
    if (notification.is_read) return
    setItems((current) => current.map((n) => (n.id === notification.id ? { ...n, is_read: true } : n)))
    setUnreadCount((count) => Math.max(count - 1, 0))
    await api.post(`/notifications/${notification.id}/read/`).catch(() => {})
  }

  const markAllRead = async () => {
    setItems((current) => current.map((n) => ({ ...n, is_read: true })))
    setUnreadCount(0)
    await api.post('/notifications/read-all/').catch(() => {})
  }

  return (
    <NotificationsContext.Provider value={{ items, unreadCount, refresh, markRead, markAllRead }}>
      {children}
    </NotificationsContext.Provider>
  )
}

export function useNotifications() {
  return useContext(NotificationsContext)
}

// Turn a notification's kind + data into a title, text and the page it opens, in the current language
function describe(notification, t, lang) {
  const d = notification.data
  switch (notification.kind) {
    case 'low_stock':
      return {
        icon: 'box',
        title: t('notifications.lowStockTitle'),
        body: t('notifications.lowStockBody', { name: d.name, qty: formatQuantity(d.stock) }),
        to: '/products?low_stock=1',
      }
    case 'out_of_stock':
      return {
        icon: 'alert',
        title: t('notifications.outOfStockTitle'),
        body: t('notifications.outOfStockBody', { name: d.name }),
        to: '/products?low_stock=1',
      }
    case 'daily_summary':
      return {
        icon: 'chart',
        title: t('notifications.dailySummaryTitle', { date: formatDate(d.date, lang) }),
        body: t('notifications.dailySummaryBody', {
          count: d.sales_count,
          revenue: formatMoney(d.revenue),
          expenses: formatMoney(d.expenses),
          net: formatMoney(d.net_profit),
        }),
        to: '/reports',
      }
    case 'recurring_expense':
      return {
        icon: 'repeat',
        title: t('notifications.recurringTitle'),
        body: t('notifications.recurringBody', {
          category: t(`expenseCategory.${d.category}`),
          amount: formatMoney(d.amount),
          date: formatDate(d.date, lang),
        }),
        to: '/expenses',
      }
    case 'subscription_ending':
      return {
        icon: 'card',
        title: t('notifications.subscriptionEndingTitle'),
        body: t(d.status === 'trial' ? 'notifications.trialEndingBody' : 'notifications.subscriptionEndingBody', {
          days: d.days_left,
        }),
        to: '/subscription',
      }
    case 'subscription_expired':
      return {
        icon: 'card',
        title: t('notifications.subscriptionExpiredTitle'),
        body: t('notifications.subscriptionExpiredBody'),
        to: '/subscription',
      }
    default:
      return { icon: 'bell', title: notification.kind, body: '', to: '/' }
  }
}

export function NotificationBell({ align = 'right' }) {
  const { t, lang } = useLanguage()
  const { items, unreadCount, markRead, markAllRead } = useNotifications()
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const ref = useRef(null)

  // Close when clicking outside or pressing Escape
  useEffect(() => {
    if (!open) return
    const onClick = (event) => ref.current && !ref.current.contains(event.target) && setOpen(false)
    const onKey = (event) => event.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const openNotification = (notification, to) => {
    markRead(notification)
    setOpen(false)
    navigate(to)
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="relative rounded-lg p-2 text-ink-2 hover:bg-soft hover:text-ink"
        aria-label={`${t('notifications.title')}${unreadCount ? ` (${unreadCount})` : ''}`}
        aria-expanded={open}
      >
        <Icon name="bell" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-bad px-1 text-[11px] font-semibold text-white">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          className={`absolute top-full z-50 mt-2 w-80 max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border border-line bg-card shadow-xl ${
            align === 'right' ? 'right-0' : 'left-0'
          }`}
        >
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <h2 className="text-sm font-semibold text-ink">{t('notifications.title')}</h2>
            {unreadCount > 0 && (
              <button onClick={markAllRead} className="text-xs font-medium text-brand-ink underline">
                {t('notifications.markAllRead')}
              </button>
            )}
          </div>
          {items.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-muted">{t('notifications.empty')}</p>
          ) : (
            <ul className="max-h-96 divide-y divide-line overflow-y-auto">
              {items.map((notification) => {
                const info = describe(notification, t, lang)
                return (
                  <li key={notification.id}>
                    <button
                      onClick={() => openNotification(notification, info.to)}
                      className={`flex w-full gap-3 px-4 py-3 text-left hover:bg-soft ${notification.is_read ? '' : 'bg-brand-soft/40'}`}
                    >
                      <span className="mt-0.5 shrink-0 text-ink-2">
                        <Icon name={info.icon} size={18} />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center gap-2 text-sm font-medium text-ink">
                          {info.title}
                          {!notification.is_read && <span className="size-2 shrink-0 rounded-full bg-brand" />}
                        </span>
                        <span className="block text-xs text-ink-2">{info.body}</span>
                        <span className="mt-1 block text-[11px] text-muted">
                          {formatDateTime(notification.created_at, lang)}
                        </span>
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
