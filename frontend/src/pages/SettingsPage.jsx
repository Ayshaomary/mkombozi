import { useState } from 'react'
import Icon from '../components/Icon'
import { Badge, Button, Card, EmptyState, ErrorBox, Input, Loading, Modal, PageHeader, SegmentedControl } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { api } from '../lib/api'
import { useApi } from '../lib/useApi'

// A small form that saves itself and shows "Saved" afterwards.
// If saveFn returns an object, the form is reset to it (e.g. to clear password fields).
function useSaveForm(initial, saveFn) {
  const [form, setForm] = useState(initial)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const field = (name) => ({
    value: form[name] ?? '',
    onChange: (e) => {
      setForm({ ...form, [name]: e.target.value })
      setSaved(false)
    },
    error: error?.fields?.[name],
  })

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const nextForm = await saveFn(form)
      if (nextForm) setForm(nextForm)
      setSaved(true)
    } catch (err) {
      setError(err)
    } finally {
      setSaving(false)
    }
  }

  return { field, submit, error, saving, saved }
}

function SaveRow({ saving, saved, error }) {
  const { t } = useLanguage()
  return (
    <div className="flex items-center gap-3">
      <Button type="submit" loading={saving}>
        {t('common.save')}
      </Button>
      {saved && (
        <span className="flex items-center gap-1 text-sm text-good">
          <Icon name="check" size={16} /> {t('common.saved')}
        </span>
      )}
      {error && Object.keys(error.fields).length === 0 && <span className="text-sm text-bad">{error.message}</span>}
    </div>
  )
}

function ProfileForm() {
  const { t } = useLanguage()
  const { user, refreshUser } = useAuth()
  const { field, submit, ...state } = useSaveForm(
    { first_name: user.first_name, last_name: user.last_name },
    async (form) => {
      await api.patch('/auth/me/', form)
      await refreshUser()
    },
  )
  return (
    <Card title={t('settings.profile')}>
      <form onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Input label={t('auth.firstName')} required {...field('first_name')} />
          <Input label={t('auth.lastName')} {...field('last_name')} />
        </div>
        <Input label={t('auth.phone')} value={user.phone} disabled readOnly />
        <SaveRow {...state} />
      </form>
    </Card>
  )
}

function BusinessForm() {
  const { t } = useLanguage()
  const { user, refreshUser } = useAuth()
  const { field, submit, ...state } = useSaveForm(
    { name: user.business.name, phone: user.business.phone, location: user.business.location },
    async (form) => {
      await api.patch('/business/', form)
      await refreshUser()
    },
  )
  return (
    <Card title={t('settings.business')}>
      <form onSubmit={submit} className="space-y-4">
        <Input label={t('auth.businessName')} required {...field('name')} />
        <Input label={t('settings.businessPhone')} type="tel" inputMode="tel" {...field('phone')} />
        <Input label={t('auth.businessLocation')} {...field('location')} />
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

function AddStaffModal({ onClose, onSaved }) {
  const { t } = useLanguage()
  const [form, setForm] = useState({ first_name: '', last_name: '', phone: '', password: '' })
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
      await api.post('/staff/', form)
      onSaved()
    } catch (err) {
      setError(err)
      setSaving(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={t('settings.addStaff')}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form="staff-form" loading={saving}>
            {t('common.save')}
          </Button>
        </>
      }
    >
      <form id="staff-form" onSubmit={submit} className="space-y-4">
        {error && Object.keys(error.fields).length === 0 && <ErrorBox error={error} />}
        <div className="grid grid-cols-2 gap-3">
          <Input label={t('auth.firstName')} required autoFocus {...field('first_name')} />
          <Input label={t('auth.lastName')} {...field('last_name')} />
        </div>
        <Input label={t('auth.phone')} type="tel" inputMode="tel" placeholder={t('auth.phonePlaceholder')} required {...field('phone')} />
        <Input
          label={t('auth.password')}
          type="password"
          autoComplete="new-password"
          hint={t('auth.passwordHint')}
          minLength={8}
          required
          {...field('password')}
        />
      </form>
    </Modal>
  )
}

function StaffSection() {
  const { t } = useLanguage()
  const { data, loading, error, reload } = useApi('/staff/')
  const [adding, setAdding] = useState(false)

  const remove = async (member) => {
    if (!window.confirm(t('settings.removeStaffConfirm', { name: member.first_name }))) return
    try {
      await api.delete(`/staff/${member.id}/`)
      reload()
    } catch (err) {
      window.alert(err.message)
    }
  }

  return (
    <Card
      title={t('settings.staff')}
      padded={false}
      action={
        <Button size="sm" icon="plus" onClick={() => setAdding(true)}>
          {t('settings.addStaff')}
        </Button>
      }
    >
      <p className="border-b border-line px-4 py-3 text-xs text-muted">{t('settings.staffHint')}</p>
      <ErrorBox error={error} onRetry={reload} />
      {loading && !data ? (
        <Loading />
      ) : data?.length ? (
        <ul className="divide-y divide-line">
          {data.map((member) => (
            <li key={member.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
              <div className="min-w-0">
                <p className="font-medium text-ink">
                  {member.first_name} {member.last_name}
                </p>
                <p className="text-xs text-muted">{member.phone}</p>
              </div>
              {member.role === 'owner' ? (
                <Badge tone="good">{t('settings.owner')}</Badge>
              ) : (
                <Button size="sm" variant="danger" onClick={() => remove(member)}>
                  {t('settings.removeStaff')}
                </Button>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState icon="users" title={t('settings.noStaff')} />
      )}
      {adding && (
        <AddStaffModal
          onClose={() => setAdding(false)}
          onSaved={() => {
            setAdding(false)
            reload()
          }}
        />
      )}
    </Card>
  )
}

export default function SettingsPage() {
  const { t, lang, setLang } = useLanguage()
  const { isOwner } = useAuth()
  return (
    <>
      <PageHeader title={t('settings.title')} />
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="space-y-5">
          <ProfileForm />
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
        {isOwner && (
          <div className="space-y-5">
            <BusinessForm />
            <StaffSection />
          </div>
        )}
      </div>
    </>
  )
}
