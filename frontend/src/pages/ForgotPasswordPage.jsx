import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Icon from '../components/Icon'
import { Button, ErrorBox, Input, Modal, PhoneInput } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { homePath } from '../lib/permissions'
import { api } from '../lib/api'
import AuthShell from './AuthShell'

// The server allows a new code after a minute
const RESEND_AFTER_SECONDS = 60

export default function ForgotPasswordPage() {
  const { t } = useLanguage()
  const { login } = useAuth()
  const navigate = useNavigate()
  const [step, setStep] = useState('phone')
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [secondsLeft, setSecondsLeft] = useState(0)
  // On a developer's computer without SMS, the server sends the code back to show here
  const [simulatedCode, setSimulatedCode] = useState(null)

  useEffect(() => {
    if (secondsLeft <= 0) return
    const timer = setTimeout(() => setSecondsLeft(secondsLeft - 1), 1000)
    return () => clearTimeout(timer)
  }, [secondsLeft])

  const sendCode = async (event) => {
    event?.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const data = await api.post('/auth/password-reset/', { phone })
      if (data?.simulated_code) setSimulatedCode(data.simulated_code)
      setStep('code')
      setSecondsLeft(RESEND_AFTER_SECONDS)
    } catch (err) {
      setError(err)
    } finally {
      setSaving(false)
    }
  }

  const resetPassword = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await api.post('/auth/password-reset/confirm/', { phone, code, new_password: password })
      const user = await login(phone, password)
      navigate(homePath(user))
    } catch (err) {
      setError(err)
      setSaving(false)
    }
  }

  return (
    <AuthShell title={t('auth.resetTitle')}>
      {step === 'phone' ? (
        <form onSubmit={sendCode} className="space-y-4">
          <p className="text-sm text-ink-2">{t('auth.resetIntro')}</p>
          <ErrorBox error={error} />
          <PhoneInput
            label={t('auth.phone')}
            autoComplete="username"
            placeholder={t('auth.phonePlaceholder')}
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            error={error?.fields?.phone}
            required
          />
          <Button type="submit" size="lg" className="w-full" loading={saving}>
            {t('auth.sendCode')}
          </Button>
        </form>
      ) : (
        <form onSubmit={resetPassword} className="space-y-4">
          <p className="text-sm text-ink-2">{t('auth.codeSent', { phone })}</p>
          <ErrorBox error={error} />
          <Input
            label={t('auth.code')}
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
            error={error?.fields?.code}
            required
          />
          <Input
            label={t('auth.newPassword')}
            type="password"
            autoComplete="new-password"
            hint={t('auth.passwordHint')}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={error?.fields?.new_password}
            required
          />
          <Button type="submit" size="lg" className="w-full" loading={saving}>
            {t('auth.setPassword')}
          </Button>
          <div className="flex flex-wrap justify-between gap-2 text-sm">
            <button
              type="button"
              className="font-semibold text-brand-ink underline disabled:text-muted disabled:no-underline"
              disabled={secondsLeft > 0 || saving}
              onClick={() => sendCode()}
            >
              {secondsLeft > 0 ? t('auth.resendIn', { seconds: secondsLeft }) : t('auth.resend')}
            </button>
            <button
              type="button"
              className="text-ink-2 underline"
              onClick={() => {
                setStep('phone')
                setCode('')
                setError(null)
              }}
            >
              {t('auth.otherNumber')}
            </button>
          </div>
        </form>
      )}
      {simulatedCode && (
        <Modal
          open
          onClose={() => setSimulatedCode(null)}
          title={t('auth.simulationTitle')}
          footer={
            <>
              <Button variant="secondary" onClick={() => setSimulatedCode(null)}>
                {t('common.close')}
              </Button>
              <Button
                onClick={() => {
                  setCode(simulatedCode)
                  setSimulatedCode(null)
                }}
              >
                {t('auth.useCode')}
              </Button>
            </>
          }
        >
          <div className="flex flex-col items-center gap-3 text-center">
            <div className="rounded-full bg-warn-soft p-3 text-warn-ink">
              <Icon name="bell" size={28} />
            </div>
            <p className="text-sm text-ink-2">{t('auth.simulationText', { phone })}</p>
            <p className="tabular text-4xl font-bold tracking-[0.3em] text-ink">{simulatedCode}</p>
            <p className="text-xs text-muted">{t('auth.simulationNote')}</p>
          </div>
        </Modal>
      )}
      <p className="mt-5 text-center text-sm">
        <Link to="/login" className="font-semibold text-brand-ink underline">
          {t('auth.backToLogin')}
        </Link>
      </p>
    </AuthShell>
  )
}
