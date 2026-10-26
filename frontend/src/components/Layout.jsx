import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import Icon from './Icon'

const NAV_ITEMS = [
  { to: '/', icon: 'home', label: 'nav.dashboard', ownerOnly: true, end: true },
  { to: '/sell', icon: 'cart', label: 'nav.newSale' },
  { to: '/sales', icon: 'receipt', label: 'nav.sales' },
  { to: '/products', icon: 'box', label: 'nav.products' },
  { to: '/expenses', icon: 'wallet', label: 'nav.expenses' },
  { to: '/reports', icon: 'chart', label: 'nav.reports', ownerOnly: true },
  { to: '/subscription', icon: 'card', label: 'nav.subscription' },
  { to: '/settings', icon: 'settings', label: 'nav.settings' },
]

export function Logo({ className = '' }) {
  return (
    <span className={`inline-flex items-center gap-2 font-bold tracking-tight text-ink ${className}`}>
      <img src="/favicon.svg" alt="" className="size-8" />
      MUKOMBOZI
    </span>
  )
}

export function LanguageToggle({ className = '' }) {
  const { lang, setLang } = useLanguage()
  return (
    <button
      onClick={() => setLang(lang === 'sw' ? 'en' : 'sw')}
      className={`inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm text-ink-2 hover:bg-soft hover:text-ink ${className}`}
    >
      <Icon name="globe" size={16} />
      {lang === 'sw' ? 'English' : 'Kiswahili'}
    </button>
  )
}

function NavList({ onNavigate }) {
  const { t } = useLanguage()
  const { isOwner } = useAuth()
  return (
    <nav className="flex flex-col gap-1">
      {NAV_ITEMS.filter((item) => isOwner || !item.ownerOnly).map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          onClick={onNavigate}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
              isActive ? 'bg-brand-soft text-brand-ink' : 'text-ink-2 hover:bg-soft hover:text-ink'
            }`
          }
        >
          <Icon name={item.icon} />
          {t(item.label)}
        </NavLink>
      ))}
    </nav>
  )
}

function UserBox() {
  const { t } = useLanguage()
  const { user, logout } = useAuth()
  return (
    <div className="border-t border-line pt-4">
      <p className="truncate text-sm font-semibold text-ink">{user.business?.name}</p>
      <p className="truncate text-xs text-muted">
        {user.first_name} · {user.role === 'owner' ? t('settings.owner') : t('settings.staffRole')}
      </p>
      <div className="mt-3 flex items-center justify-between">
        <LanguageToggle className="-ml-2" />
        <button
          onClick={logout}
          className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm text-ink-2 hover:bg-soft hover:text-ink"
        >
          <Icon name="logout" size={16} />
          {t('nav.logout')}
        </button>
      </div>
    </div>
  )
}

function SubscriptionBanner() {
  const { t } = useLanguage()
  const { subscription } = useAuth()
  if (!subscription) return null

  let message = null
  let tone = 'warn'
  if (!subscription.is_valid) {
    message = t('subscription.bannerExpired')
    tone = 'bad'
  } else if (subscription.status === 'trial' && subscription.days_left <= 7) {
    message = t('subscription.bannerTrial', { days: subscription.days_left })
  } else if (subscription.status === 'active' && subscription.days_left <= 5) {
    message = t('subscription.bannerEnding', { days: subscription.days_left })
  }
  if (!message) return null

  const colors = tone === 'bad' ? 'bg-bad-soft text-bad' : 'bg-warn-soft text-warn-ink'
  return (
    <div className={`flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-sm ${colors}`}>
      <span className="flex items-center gap-2">
        <Icon name="alert" size={16} />
        {message}
      </span>
      <Link to="/subscription" className="font-semibold underline">
        {t('subscription.renew')}
      </Link>
    </div>
  )
}

export default function Layout() {
  const { t } = useLanguage()
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="min-h-screen md:flex">
      {/* Sidebar on computers */}
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col justify-between border-r border-line bg-card p-4 md:flex">
        <div>
          <Link to="/" className="mb-6 block px-2">
            <Logo />
          </Link>
          <NavList />
        </div>
        <UserBox />
      </aside>

      {/* Top bar on phones */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-card px-4 py-2 md:hidden">
        <Link to="/">
          <Logo />
        </Link>
        <button
          onClick={() => setMenuOpen(true)}
          className="rounded-lg p-2 text-ink-2 hover:bg-soft"
          aria-label={t('nav.menu')}
        >
          <Icon name="menu" />
        </button>
      </header>

      {/* Slide-out menu on phones */}
      {menuOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMenuOpen(false)} />
          <div className="absolute inset-y-0 right-0 flex w-72 max-w-[85vw] flex-col justify-between bg-card p-4">
            <div>
              <div className="mb-4 flex items-center justify-between">
                <Logo />
                <button
                  onClick={() => setMenuOpen(false)}
                  className="rounded-lg p-2 text-ink-2 hover:bg-soft"
                  aria-label={t('common.close')}
                >
                  <Icon name="x" />
                </button>
              </div>
              <NavList onNavigate={() => setMenuOpen(false)} />
            </div>
            <UserBox />
          </div>
        </div>
      )}

      <div className="min-w-0 flex-1">
        <SubscriptionBanner />
        <main className="mx-auto w-full max-w-6xl px-4 py-5 sm:px-6 sm:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
