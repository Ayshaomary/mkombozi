import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Badge,
  Button,
  Card,
  Checkbox,
  EmptyState,
  ErrorBox,
  Input,
  Loading,
  Modal,
  PageHeader,
  SegmentedControl,
  Select,
  StatTile,
} from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { api } from '../lib/api'
import { formatDate, formatDateTime, formatMoney } from '../lib/format'
import { useApi, usePaginated } from '../lib/useApi'
import { useDebounce } from '../lib/useDebounce'

// Same as ActivityLog.Action in activity/models.py
const ACTIONS = ['create', 'update', 'delete', 'login', 'login_failed', 'password', 'other']
const ACTION_TONES = { create: 'good', delete: 'bad', login_failed: 'bad', password: 'warn' }

function Overview() {
  const { t, lang } = useLanguage()
  const { data, loading, error, reload } = useApi('/admin/overview/')
  if (loading && !data) return <Loading />
  if (error) return <ErrorBox error={error} onRetry={reload} />

  const subs = data.subscriptions
  return (
    <>
      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-3">
        <StatTile
          label={t('admin.businesses')}
          value={data.businesses}
          sub={t('admin.newThisWeek', { count: data.new_businesses_week })}
          subTone={data.new_businesses_week > 0 ? 'good' : undefined}
        />
        <StatTile
          label={t('admin.usersCount')}
          value={data.users}
          sub={t('admin.activeUsers', { count: data.active_users_month })}
        />
        <StatTile
          label={t('admin.revenueMonth')}
          value={formatMoney(data.revenue_month)}
          sub={t('admin.revenueTotal', { amount: formatMoney(data.revenue_total) })}
        />
        <StatTile
          label={t('admin.paidSubs')}
          value={subs.active}
          sub={t('admin.subsSub', { trial: subs.trial, expired: subs.expired })}
        />
        <StatTile label={t('admin.pendingPayments')} value={data.pending_payments} />
        <StatTile
          label={t('admin.activityToday')}
          value={data.activities_today}
          sub={t('admin.failedLogins', { count: data.failed_logins_today })}
          subTone={data.failed_logins_today > 0 ? 'bad' : undefined}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title={t('admin.recentShops')} padded={false}>
          {data.recent_businesses.length === 0 ? (
            <EmptyState icon="users" title={t('admin.noShops')} />
          ) : (
            <ul className="divide-y divide-line">
              {data.recent_businesses.map((b) => (
                <li key={b.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-ink">{b.name}</p>
                    <p className="truncate text-xs text-muted">
                      {[t(`shopTypes.${b.business_type}`), b.location].filter(Boolean).join(' · ')}
                    </p>
                  </div>
                  <span className="shrink-0 text-xs text-muted">{formatDate(b.created_at, lang)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title={t('admin.shopTypes')} padded={false}>
          <ul className="divide-y divide-line">
            {data.business_types.map((row) => (
              <li key={row.business_type} className="flex items-center justify-between px-4 py-3 text-sm">
                <span className="text-ink">{t(`shopTypes.${row.business_type}`)}</span>
                <span className="tabular font-semibold text-ink">{row.count}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  )
}

function ActivityTab({ userFilter, onClearUser }) {
  const { t, lang } = useLanguage()
  const [search, setSearch] = useState('')
  const [action, setAction] = useState('')
  const [business, setBusiness] = useState('')
  const debouncedSearch = useDebounce(search)
  const businesses = useApi('/admin/businesses/')
  const activities = usePaginated('/admin/activities/', {
    search: debouncedSearch,
    action,
    business,
    user: userFilter?.id,
  })

  return (
    <>
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Input
          type="search"
          placeholder={t('admin.search')}
          aria-label={t('admin.search')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Select
          aria-label={t('admin.allActions')}
          value={action}
          onChange={(e) => setAction(e.target.value)}
          options={[
            { value: '', label: t('admin.allActions') },
            ...ACTIONS.map((a) => ({ value: a, label: t(`admin.actions.${a}`) })),
          ]}
        />
        <Select
          aria-label={t('admin.allShops')}
          value={business}
          onChange={(e) => setBusiness(e.target.value)}
          options={[
            { value: '', label: t('admin.allShops') },
            ...(businesses.data ?? []).map((b) => ({ value: b.id, label: b.name })),
          ]}
        />
      </div>
      {userFilter && (
        <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
          <Badge>{t('admin.filteredUser', { name: userFilter.name })}</Badge>
          <button className="text-brand-ink underline" onClick={onClearUser}>
            {t('admin.clearFilter')}
          </button>
        </div>
      )}

      <Card padded={false}>
        <ErrorBox error={activities.error} onRetry={activities.reload} />
        {activities.loading && activities.items.length === 0 ? (
          <Loading />
        ) : activities.items.length === 0 ? (
          <EmptyState icon="history" title={t('admin.noActivity')} />
        ) : (
          <ul className="divide-y divide-line">
            {activities.items.map((entry) => (
              <li key={entry.id} className="flex items-start justify-between gap-3 px-4 py-3 text-sm">
                <div className="min-w-0">
                  <p className="font-medium break-words text-ink">{entry.summary}</p>
                  <p className="text-xs break-words text-muted">
                    {[
                      formatDateTime(entry.created_at, lang),
                      entry.user_name ? `${entry.user_name} (${entry.user_phone})` : entry.user_phone,
                      entry.business_name,
                      entry.ip_address && `IP ${entry.ip_address}`,
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </p>
                </div>
                <Badge tone={ACTION_TONES[entry.action]}>{t(`admin.actions.${entry.action}`)}</Badge>
              </li>
            ))}
          </ul>
        )}
      </Card>
      {activities.hasMore && (
        <div className="mt-4 text-center">
          <Button variant="secondary" loading={activities.loading} onClick={activities.loadMore}>
            {t('common.loadMore')}
          </Button>
        </div>
      )}
    </>
  )
}

function EditUserModal({ user, onClose, onSaved }) {
  const { t } = useLanguage()
  const { user: me } = useAuth()
  const [form, setForm] = useState({ role: user.role, is_active: user.is_active, is_staff: user.is_staff })
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const name = [user.first_name, user.last_name].filter(Boolean).join(' ') || user.phone

  const save = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      onSaved(await api.patch(`/admin/users/${user.id}/`, form))
    } catch (err) {
      setError(err)
      setSaving(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={t('admin.editTitle', { name })}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form="admin-user-form" loading={saving}>
            {t('common.save')}
          </Button>
        </>
      }
    >
      <form id="admin-user-form" onSubmit={save} className="space-y-4">
        <p className="text-sm text-ink-2">
          {user.phone} · {user.business_name ?? t('admin.noShop')}
        </p>
        <ErrorBox error={error} />
        <Select
          label={t('admin.role')}
          hint={user.business ? undefined : t('admin.noShopRole')}
          disabled={!user.business}
          value={form.role}
          onChange={(e) => setForm({ ...form, role: e.target.value })}
          options={[
            { value: 'owner', label: t('settings.owner') },
            { value: 'staff', label: t('settings.staffRole') },
          ]}
        />
        <div>
          <Checkbox
            label={t('admin.active')}
            checked={form.is_active}
            onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
          />
          <p className="mt-1 text-xs text-muted">{t('admin.activeHint')}</p>
        </div>
        <div>
          <Checkbox
            label={t('admin.adminAccess')}
            checked={form.is_staff}
            disabled={!me.is_superuser}
            onChange={(e) => setForm({ ...form, is_staff: e.target.checked })}
          />
          {!me.is_superuser && <p className="mt-1 text-xs text-muted">{t('admin.superuserOnly')}</p>}
        </div>
      </form>
    </Modal>
  )
}

function UsersTab({ onShowActivity }) {
  const { t, lang } = useLanguage()
  const [search, setSearch] = useState('')
  const [role, setRole] = useState('')
  const [editing, setEditing] = useState(null)
  const debouncedSearch = useDebounce(search)
  const users = usePaginated('/admin/users/', { search: debouncedSearch, role })

  const fullName = (u) => [u.first_name, u.last_name].filter(Boolean).join(' ') || u.phone

  return (
    <>
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Input
          className="sm:col-span-2"
          type="search"
          placeholder={t('admin.search')}
          aria-label={t('admin.search')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Select
          aria-label={t('admin.allRoles')}
          value={role}
          onChange={(e) => setRole(e.target.value)}
          options={[
            { value: '', label: t('admin.allRoles') },
            { value: 'owner', label: t('settings.owner') },
            { value: 'staff', label: t('settings.staffRole') },
            { value: 'admin', label: t('admin.admins') },
          ]}
        />
      </div>

      <Card padded={false}>
        <ErrorBox error={users.error} onRetry={users.reload} />
        {users.loading && users.items.length === 0 ? (
          <Loading />
        ) : users.items.length === 0 ? (
          <EmptyState icon="users" title={t('admin.noUsers')} />
        ) : (
          <ul className="divide-y divide-line">
            {users.items.map((u) => (
              <li key={u.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm">
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-2 font-medium text-ink">
                    {fullName(u)}
                    {u.business && <Badge>{u.role === 'owner' ? t('settings.owner') : t('settings.staffRole')}</Badge>}
                    {u.is_staff && <Badge tone="good">{t('admin.admin')}</Badge>}
                    {!u.is_active && <Badge tone="bad">{t('admin.inactive')}</Badge>}
                  </p>
                  <p className="truncate text-xs text-muted">
                    {u.phone} · {u.business_name ?? t('admin.noShop')} · {t('admin.joined', { date: formatDate(u.date_joined, lang) })}
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button size="sm" variant="secondary" icon="history" onClick={() => onShowActivity(u, fullName(u))}>
                    {t('admin.viewActivity')}
                  </Button>
                  <Button size="sm" variant="secondary" icon="edit" onClick={() => setEditing(u)}>
                    {t('admin.edit')}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
      {users.hasMore && (
        <div className="mt-4 text-center">
          <Button variant="secondary" loading={users.loading} onClick={users.loadMore}>
            {t('common.loadMore')}
          </Button>
        </div>
      )}

      {editing && (
        <EditUserModal
          user={editing}
          onClose={() => setEditing(null)}
          onSaved={(saved) => {
            users.setItems((items) => items.map((item) => (item.id === saved.id ? saved : item)))
            setEditing(null)
          }}
        />
      )}
    </>
  )
}

export default function AdminDashboardPage() {
  const { t } = useLanguage()
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') || 'overview'
  const userFilter = params.get('user') ? { id: params.get('user'), name: params.get('name') || params.get('user') } : null

  return (
    <>
      <PageHeader title={t('admin.title')} subtitle={t('admin.subtitle')} />
      <div className="mb-5">
        <SegmentedControl
          label={t('admin.title')}
          value={tab}
          onChange={(value) => setParams({ tab: value })}
          options={[
            { value: 'overview', label: t('admin.overview') },
            { value: 'activity', label: t('admin.activity') },
            { value: 'users', label: t('admin.users') },
          ]}
        />
      </div>
      {tab === 'overview' && <Overview />}
      {tab === 'activity' && (
        <ActivityTab
          key={userFilter?.id ?? 'all'}
          userFilter={userFilter}
          onClearUser={() => setParams({ tab: 'activity' })}
        />
      )}
      {tab === 'users' && (
        <UsersTab onShowActivity={(user, name) => setParams({ tab: 'activity', user: user.id, name })} />
      )}
    </>
  )
}
