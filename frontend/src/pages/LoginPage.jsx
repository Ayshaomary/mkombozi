import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button, ErrorBox, Input, PhoneInput } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { homePath } from '../lib/permissions'
import AuthShell from './AuthShell'

export default function LoginPage() {
  const { t } = useLanguage()
  const { login } = useAuth()
  const navigate = useNavigate()
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const user = await login(phone, password)
      navigate(homePath(user))
    } catch (err) {
      setError(err)
      setSaving(false)
    }
  }

  return (
    <AuthShell title={t('auth.welcomeBack')}>
      <form onSubmit={submit} className="space-y-4">
        <ErrorBox error={error} />
        <PhoneInput
          label={t('auth.phone')}
          autoComplete="username"
          placeholder={t('auth.phonePlaceholder')}
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          required
        />
        <Input
          label={t('auth.password')}
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <p className="-mt-2 text-right text-sm">
          <Link to="/forgot-password" className="text-brand-ink underline">
            {t('auth.forgotPassword')}
          </Link>
        </p>
        <Button type="submit" size="lg" className="w-full" loading={saving}>
          {t('auth.login')}
        </Button>
      </form>
      <p className="mt-5 text-center text-sm text-ink-2">
        {t('auth.noAccount')}{' '}
        <Link to="/register" className="font-semibold text-brand-ink underline">
          {t('auth.register')}
        </Link>
      </p>
    </AuthShell>
  )
}
