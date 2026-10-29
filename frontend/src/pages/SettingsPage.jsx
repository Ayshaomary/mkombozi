import { useRef, useState } from 'react'
import Avatar from '../components/Avatar'
import Icon from '../components/Icon'
import PermissionPicker from '../components/PermissionPicker'
import { Badge, Button, Card, EmptyState, ErrorBox, Input, Loading, Modal, PageHeader, PhoneInput, SaveRow, Select, TextArea } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { api } from '../lib/api'
import { PERMISSION_PRESETS, SHOP_TYPES } from '../lib/constants'
import { presetOf } from '../lib/permissions'
import { logoToDataUrl, logoUrl } from '../lib/photo'
import { useApi } from '../lib/useApi'
import { useSaveForm } from '../lib/useSaveForm'

// The logo printed at the top of lists and receipts. Saved as soon as it is chosen, like a profile photo.
function LogoPicker() {
  const { t } = useLanguage()
  const { user, refreshUser } = useAuth()
  const fileInput = useRef(null)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const key = user.business.logo_key

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
        image = await logoToDataUrl(file)
      } catch {
        throw new Error(t('settings.logoError'))
      }
      await api.put('/business/logo/', { image })
    })
  }

  return (
    <div>
      <p className="mb-1 text-sm font-medium text-ink-2">{t('settings.logo')}</p>
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex h-20 w-32 items-center justify-center rounded-lg border border-line-strong bg-white p-2">
          {key ? (
            <img src={logoUrl(key)} alt="" className="max-h-full max-w-full object-contain" />
          ) : (
            <Icon name="camera" size={24} className="text-muted" />
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <input ref={fileInput} type="file" accept="image/*" className="hidden" onChange={upload} />
          <Button size="sm" icon="camera" loading={saving} onClick={() => fileInput.current.click()}>
            {key ? t('settings.changeLogo') : t('settings.addLogo')}
          </Button>
          {key && (
            <Button
              size="sm"
              variant="secondary"
              disabled={saving}
              onClick={() => window.confirm(t('settings.removeLogoConfirm')) && run(() => api.delete('/business/logo/'))}
            >
              {t('settings.removeLogo')}
            </Button>
          )}
        </div>
      </div>
      <div className="mt-2">
        <ErrorBox error={error} />
      </div>
    </div>
  )
}

function BusinessForm() {
  const { t } = useLanguage()
  const { user, refreshUser } = useAuth()
  const { field, submit, ...state } = useSaveForm(
    {
      name: user.business.name,
      business_type: user.business.business_type,
      phone: user.business.phone,
      location: user.business.location,
      description: user.business.description,
      address: user.business.address,
      email: user.business.email,
    },
    async (form) => {
      await api.patch('/business/', form)
      await refreshUser()
    },
  )
  return (
    <Card title={t('settings.business')}>
      <LogoPicker />
      <form onSubmit={submit} className="mt-4 space-y-4">
        <Input label={t('auth.businessName')} required {...field('name')} />
        <Select
          label={t('auth.shopType')}
          hint={t('settings.shopTypeHint')}
          options={SHOP_TYPES.map((type) => ({ value: type, label: t(`shopTypes.${type}`) }))}
          {...field('business_type')}
        />
        <PhoneInput label={t('settings.businessPhone')} {...field('phone')} />
        <Input label={t('auth.businessLocation')} {...field('location')} />
        <TextArea label={t('settings.businessDescription')} maxLength={300} {...field('description')} />
        <Input label={t('settings.businessAddress')} maxLength={255} {...field('address')} />
        <Input label={t('settings.businessEmail')} type="email" {...field('email')} />
        <p className="text-xs text-muted">{t('settings.letterheadHint')}</p>
        <SaveRow {...state} />
      </form>
    </Card>
  )
}

function AddStaffModal({ onClose, onSaved }) {
  const { t } = useLanguage()
  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    phone: '',
    password: '',
    permissions: PERMISSION_PRESETS.salesOnly,
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
        <div>
          <p className="mb-2 text-sm font-semibold text-ink">{t('access.whatCanDo')}</p>
          <PermissionPicker value={form.permissions} onChange={(permissions) => setForm({ ...form, permissions })} />
        </div>
      </form>
    </Modal>
  )
}

function AccessModal({ member, onClose, onSaved }) {
  const { t } = useLanguage()
  const [permissions, setPermissions] = useState(member.permissions)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      await api.patch(`/staff/${member.id}/`, { permissions })
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
      title={t('access.title', { name: member.first_name })}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button loading={saving} onClick={save}>
            {t('common.save')}
          </Button>
        </>
      }
    >
      <ErrorBox error={error} />
      <PermissionPicker value={permissions} onChange={setPermissions} />
    </Modal>
  )
}

function StaffSection() {
  const { t } = useLanguage()
  const { data, loading, error, reload } = useApi('/staff/')
  const [adding, setAdding] = useState(false)
  const [editingAccess, setEditingAccess] = useState(null)

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
                  {member.role !== 'owner' && (
                    <p className="text-xs text-ink-2">
                      {presetOf(member.permissions) === 'custom'
                        ? member.permissions.map((p) => t(`access.perm.${p}`)).join(', ') || t('access.nothing')
                        : t(`access.preset.${presetOf(member.permissions)}`)}
                    </p>
                  )}
                </div>
              </div>
              {member.role === 'owner' ? (
                <Badge tone="good">{t('settings.owner')}</Badge>
              ) : (
                <div className="flex shrink-0 gap-2">
                  <Button size="sm" variant="secondary" onClick={() => setEditingAccess(member)}>
                    {t('access.button')}
                  </Button>
                  <Button size="sm" variant="danger" onClick={() => remove(member)}>
                    {t('settings.removeStaff')}
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState icon="users" title={t('settings.noStaff')} />
      )}
      {editingAccess && (
        <AccessModal
          member={editingAccess}
          onClose={() => setEditingAccess(null)}
          onSaved={() => {
            setEditingAccess(null)
            reload()
          }}
        />
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
