import { useRef, useState } from 'react'
import Avatar from '../components/Avatar'
import Icon from '../components/Icon'
import { Button, Card, ErrorBox, Input, PageHeader, SaveRow, SegmentedControl } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { api } from '../lib/api'
import { photoToDataUrl } from '../lib/photo'
import { useSaveForm } from '../lib/useSaveForm'

function PhotoCard() {
  const { t } = useLanguage()
  const { user, refreshUser } = useAuth()
  const fileInput = useRef(null)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const run = async (action) => {
    setSaving(true)
    setError(null)
    try {
      await action()
      await refreshUser()
    } catch (err) {
      setError(err)
    } finally {
      setSaving(false)
    }
  }

  const upload = (event) => {
    const file = event.target.files[0]
    // Lets the same file be chosen again later
    event.target.value = ''
    if (!file) return
    run(async () => {
      let image
      try {
        image = await photoToDataUrl(file)
      } catch {
        throw new Error(t('profile.photoError'))
      }
      await api.put('/auth/me/photo/', { image })
    })
  }

  const remove = () => {
    if (window.confirm(t('profile.removeConfirm'))) run(() => api.delete('/auth/me/photo/'))
  }

  const name = [user.first_name, user.last_name].filter(Boolean).join(' ')
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-5">
        <Avatar user={user} size={96} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-lg font-semibold text-ink">{name}</p>
          <p className="text-sm text-muted">{user.phone}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <input ref={fileInput} type="file" accept="image/*" className="hidden" onChange={upload} />
            <Button size="sm" icon="camera" loading={saving} onClick={() => fileInput.current.click()}>
              {user.avatar_key ? t('profile.changePhoto') : t('profile.addPhoto')}
            </Button>
            {user.avatar_key && (
              <Button size="sm" variant="secondary" disabled={saving} onClick={remove}>
                {t('profile.removePhoto')}
              </Button>
            )}
          </div>
        </div>
      </div>
      <p className="mt-3 flex items-start gap-2 text-xs text-muted">
        <Icon name="alert" size={14} className="mt-0.5 shrink-0" />
        {t('profile.photoHint')}
      </p>
      <div className="mt-3">
        <ErrorBox error={error} />
      </div>
    </Card>
  )
}

function DetailsForm() {
  const { t } = useLanguage()
  const { user, refreshUser } = useAuth()
  const { field, submit, ...state } = useSaveForm(
    { first_name: user.first_name, last_name: user.last_name, email: user.email ?? '' },
    async (form) => {
      await api.patch('/auth/me/', form)
      await refreshUser()
    },
  )
  return (
    <Card title={t('profile.details')}>
      <form onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Input label={t('auth.firstName')} required {...field('first_name')} />
          <Input label={t('auth.lastName')} {...field('last_name')} />
        </div>
        <Input
          label={t('profile.email')}
          type="email"
          autoComplete="email"
          hint={t('profile.emailHint')}
          {...field('email')}
        />
        <Input label={t('auth.phone')} value={user.phone} disabled readOnly hint={t('profile.phoneHint')} />
        <SaveRow {...state} />
      </form>
    </Card>
  )
}

function PasswordForm() {
  const { t } = useLanguage()
  const { field, submit, ...state } = useSaveForm({ old_password: '', new_password: '' }, async (form) => {
    await api.post('/auth/change-password/', form)
    return { old_password: '', new_password: '' }
  })
  return (
    <Card title={t('settings.changePassword')}>
      <form onSubmit={submit} className="space-y-4">
        <Input label={t('settings.oldPassword')} type="password" autoComplete="current-password" required {...field('old_password')} />
        <Input
          label={t('settings.newPassword')}
          type="password"
          autoComplete="new-password"
          hint={t('auth.passwordHint')}
          minLength={8}
          required
          {...field('new_password')}
        />
        <SaveRow {...state} />
      </form>
    </Card>
  )
}

export default function ProfilePage() {
  const { t, lang, setLang } = useLanguage()
  return (
    <>
      <PageHeader title={t('profile.title')} />
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="space-y-5">
          <PhotoCard />
          <DetailsForm />
        </div>
        <div className="space-y-5">
          <Card title={t('settings.language')}>
            <SegmentedControl
              value={lang}
              onChange={setLang}
              label={t('settings.language')}
              options={[
                { value: 'sw', label: 'Kiswahili' },
                { value: 'en', label: 'English' },
              ]}
            />
          </Card>
          <PasswordForm />
        </div>
      </div>
    </>
  )
}
