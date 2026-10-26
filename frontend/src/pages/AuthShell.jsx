import { LanguageToggle, Logo } from '../components/Layout'
import { useLanguage } from '../i18n/LanguageContext'

// The frame around the login and register forms
export default function AuthShell({ title, children }) {
  const { t } = useLanguage()
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-between">
          <Logo />
          <LanguageToggle />
        </div>
        <p className="mb-6 text-sm text-ink-2">{t('auth.tagline')}</p>
        <div className="rounded-2xl border border-line bg-card p-6">
          <h1 className="mb-5 text-lg font-semibold text-ink">{title}</h1>
          {children}
        </div>
      </div>
    </div>
  )
}
