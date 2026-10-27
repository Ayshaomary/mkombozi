import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button, ErrorBox, Input, PhoneInput } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import AuthShell from './AuthShell'

export default function RegisterPage() {
  const { t } = useLanguage()
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    business_name: '',
    business_location: '',
    first_name: '',
    last_name: '',
    phone: '',
    password: '',
  })
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const field = (name) => ({
    value: form[name],
    onChange: (e) => setForm({ ...form, [name]: e.target.value }),
    error: error?.fields?.[name],
  })

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await register(form)
      navigate('/')
    } catch (err) {
      setError(err)
      setSaving(false)
    }
  }

  const hasFieldErrors = error && Object.keys(error.fields).length > 0

  return (
    <AuthShell title={t('auth.startFree')}>
      <form onSubmit={submit} className="space-y-4">
        {!hasFieldErrors && <ErrorBox error={error} />}
        <Input label={t('auth.businessName')} required {...field('business_name')} />
        <Input label={t('auth.businessLocation')} {...field('business_location')} />
        <div className="grid grid-cols-2 gap-3">
          <Input label={t('auth.firstName')} autoComplete="given-name" required {...field('first_name')} />
          <Input label={t('auth.lastName')} autoComplete="family-name" {...field('last_name')} />
        </div>
        <PhoneInput
          label={t('auth.phone')}
          autoComplete="username"
          placeholder={t('auth.phonePlaceholder')}
          required
          {...field('phone')}
        />
        <Input
          label={t('auth.password')}
          type="password"
          autoComplete="new-password"
          hint={t('auth.passwordHint')}
          minLength={8}
          required
          {...field('password')}
        />
        <Button type="submit" size="lg" className="w-full" loading={saving}>
          {t('auth.register')}
        </Button>
        <p className="text-center text-xs text-muted">{t('auth.trialNote')}</p>
      </form>
      <p className="mt-5 text-center text-sm text-ink-2">
        {t('auth.haveAccount')}{' '}
        <Link to="/login" className="font-semibold text-brand-ink underline">
          {t('auth.login')}
        </Link>
      </p>
    </AuthShell>
  )
}
