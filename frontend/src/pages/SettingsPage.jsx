import { useState } from 'react'
import Avatar from '../components/Avatar'
import { Badge, Button, Card, EmptyState, ErrorBox, Input, Loading, Modal, PageHeader, PhoneInput, SaveRow, Select } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { api } from '../lib/api'
import { SHOP_TYPES } from '../lib/constants'
import { useApi } from '../lib/useApi'
import { useSaveForm } from '../lib/useSaveForm'

function BusinessForm() {
  const { t } = useLanguage()
  const { user, refreshUser } = useAuth()
  const { field, submit, ...state } = useSaveForm(
    {
      name: user.business.name,
      business_type: user.business.business_type,
      phone: user.business.phone,
      location: user.business.location,
    },
    async (form) => {
      await api.patch('/business/', form)
      await refreshUser()
    },
  )
  return (
    <Card title={t('settings.business')}>
      <form onSubmit={submit} className="space-y-4">
        <Input label={t('auth.businessName')} required {...field('name')} />
        <Select
          label={t('auth.shopType')}
          hint={t('settings.shopTypeHint')}
          options={SHOP_TYPES.map((type) => ({ value: type, label: t(`shopTypes.${type}`) }))}
          {...field('business_type')}
        />
        <PhoneInput label={t('settings.businessPhone')} {...field('phone')} />
        <Input label={t('auth.businessLocation')} {...field('location')} />
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
        <PhoneInput label={t('auth.phone')} placeholder={t('auth.phonePlaceholder')} required {...field('phone')} />
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
              <div className="flex min-w-0 items-center gap-3">
                <Avatar user={member} size={36} />
                <div className="min-w-0">
                  <p className="font-medium text-ink">
                    {member.first_name} {member.last_name}
                  </p>
                  <p className="text-xs text-muted">{member.phone}</p>
                </div>
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

// The shop's settings, for the owner. Personal settings (photo, name, password) are on the profile page.
export default function SettingsPage() {
  const { t } = useLanguage()
  return (
    <>
      <PageHeader title={t('settings.title')} />
      <div className="grid gap-5 lg:grid-cols-2">
        <BusinessForm />
        <StaffSection />
      </div>
    </>
  )
}
