import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import Icon from '../components/Icon'
import { useNotifications } from '../components/Notifications'
import { Badge, Button, Card, EmptyState, ErrorBox, Input, Loading, Modal, PageHeader, PeriodFilter, Select } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { api } from '../lib/api'
import { EXPENSE_CATEGORIES } from '../lib/constants'
import { formatDate, formatMoney, todayISO } from '../lib/format'
import { useApi, usePaginated } from '../lib/useApi'

function ExpenseFormModal({ expense, onClose, onSaved }) {
  const { t } = useLanguage()
  const isNew = !expense.id
  const [form, setForm] = useState(() => ({
    category: expense.category ?? 'other',
    amount: expense.amount ? String(Number(expense.amount)) : '',
    date: expense.date ?? todayISO(),
    description: expense.description ?? '',
  }))
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const field = (name) => ({
    value: form[name],
    onChange: (e) => setForm({ ...form, [name]: e.target.value }),
    error: error?.fields?.[name],
  })

  const save = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      if (isNew) await api.post('/expenses/', form)
      else await api.patch(`/expenses/${expense.id}/`, form)
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
      title={isNew ? t('expense.add') : t('expense.editTitle')}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form="expense-form" loading={saving}>
            {t('common.save')}
          </Button>
        </>
      }
    >
      <form id="expense-form" onSubmit={save} className="space-y-4">
        {error && Object.keys(error.fields).length === 0 && <ErrorBox error={error} />}
        <Select
          label={t('expense.category')}
          options={EXPENSE_CATEGORIES.map((c) => ({ value: c, label: t(`expenseCategory.${c}`) }))}
          {...field('category')}
        />
        <div className="grid grid-cols-2 gap-3">
          <Input
            label={t('common.amount')}
            type="number"
            min="0"
            step="any"
            inputMode="decimal"
            required
            autoFocus
            {...field('amount')}
          />
          <Input label={t('common.date')} type="date" max={todayISO()} required {...field('date')} />
        </div>
        <Input label={`${t('expense.description')} (${t('common.optional')})`} {...field('description')} />
        <p className="flex gap-2 rounded-lg bg-soft p-3 text-xs text-ink-2">
          <Icon name="alert" size={16} className="shrink-0" />
          {t('expense.stockNote')}
        </p>
      </form>
    </Modal>
  )
}

const FREQUENCIES = ['monthly', 'weekly', 'daily']

function RecurringExpensesModal({ onClose, onChanged }) {
  const { t, lang } = useLanguage()
  const { data, error, reload } = useApi('/recurring-expenses/')
  const [form, setForm] = useState({ category: 'rent', amount: '', frequency: 'monthly', start_date: todayISO(), description: '' })
  const [formError, setFormError] = useState(null)
  const [saving, setSaving] = useState(false)

  const field = (name) => ({
    value: form[name],
    onChange: (e) => setForm({ ...form, [name]: e.target.value }),
    error: formError?.fields?.[name],
  })

  const changed = () => {
    reload()
    onChanged()
  }

  const add = async (event) => {
    event.preventDefault()
    setSaving(true)
    setFormError(null)
    try {
      await api.post('/recurring-expenses/', form)
      setForm({ ...form, amount: '', description: '' })
      changed()
    } catch (err) {
      setFormError(err)
    } finally {
      setSaving(false)
    }
  }

  const toggle = async (recurring) => {
    await api.patch(`/recurring-expenses/${recurring.id}/`, { is_active: !recurring.is_active }).catch(setFormError)
    changed()
  }

  const remove = async (recurring) => {
    if (!window.confirm(t('recurring.deleteConfirm'))) return
    await api.delete(`/recurring-expenses/${recurring.id}/`).catch(setFormError)
    changed()
  }

  return (
    <Modal open onClose={onClose} title={t('recurring.title')} wide>
      <form onSubmit={add} className="space-y-3 rounded-xl bg-soft p-4">
        <p className="text-sm font-semibold text-ink">{t('recurring.add')}</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Select
            label={t('expense.category')}
            options={EXPENSE_CATEGORIES.map((c) => ({ value: c, label: t(`expenseCategory.${c}`) }))}
            {...field('category')}
          />
          <Input label={t('common.amount')} type="number" min="0" step="any" inputMode="decimal" required {...field('amount')} />
          <Select
            label={t('recurring.frequency')}
            options={FREQUENCIES.map((f) => ({ value: f, label: t(`frequency.${f}`) }))}
            {...field('frequency')}
          />
          <Input label={t('recurring.startDate')} type="date" required {...field('start_date')} />
        </div>
        <Input label={`${t('expense.description')} (${t('common.optional')})`} {...field('description')} />
        <p className="text-xs text-ink-2">{t('recurring.hint')}</p>
        {formError && Object.keys(formError.fields).length === 0 && <ErrorBox error={formError} />}
        <Button type="submit" icon="plus" loading={saving}>
          {t('common.add')}
        </Button>
      </form>

      <ErrorBox error={error} onRetry={reload} />
      {!data ? (
        <Loading />
      ) : data.length === 0 ? (
        <EmptyState icon="repeat" title={t('recurring.empty')} />
      ) : (
        <ul className="mt-2 divide-y divide-line">
          {data.map((recurring) => (
            <li key={recurring.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-ink">
                  {t(`expenseCategory.${recurring.category}`)} · {formatMoney(recurring.amount)}
                  {!recurring.is_active && <Badge>{t('recurring.paused')}</Badge>}
                </p>
                <p className="text-xs text-muted">
                  {t(`frequency.${recurring.frequency}`)}
                  {recurring.is_active && ` · ${t('recurring.next', { date: formatDate(recurring.next_date, lang) })}`}
                  {recurring.description && ` · ${recurring.description}`}
                </p>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="secondary" onClick={() => toggle(recurring)}>
                  {recurring.is_active ? t('recurring.pause') : t('recurring.resume')}
                </Button>
                <Button size="sm" variant="danger" icon="trash" onClick={() => remove(recurring)} aria-label={t('common.delete')} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </Modal>
  )
}

export default function ExpensesPage() {
  const { t, lang } = useLanguage()
  const { isOwner } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const [period, setPeriod] = useState('month')
  const [category, setCategory] = useState('')
  const [editing, setEditing] = useState(() => (searchParams.get('add') === '1' ? {} : null))
  const [showRecurring, setShowRecurring] = useState(false)
  const notifications = useNotifications()

  const expenses = usePaginated('/expenses/', { period: period === 'all' ? '' : period, category })

  const closeForm = () => {
    setEditing(null)
    if (searchParams.has('add')) setSearchParams({}, { replace: true })
  }

  const remove = async (expense) => {
    if (!window.confirm(t('common.confirmDelete'))) return
    try {
      await api.delete(`/expenses/${expense.id}/`)
      expenses.reload()
    } catch (err) {
      window.alert(err.message)
    }
  }

  return (
    <>
      <PageHeader
        title={t('expense.title')}
        actions={
          <>
            {isOwner && (
              <Button variant="secondary" icon="repeat" onClick={() => setShowRecurring(true)}>
                {t('recurring.title')}
              </Button>
            )}
            <Button icon="plus" onClick={() => setEditing({})}>
              {t('expense.add')}
            </Button>
          </>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <PeriodFilter value={period} onChange={setPeriod} includeAll />
        <Select
          aria-label={t('expense.category')}
          className="w-48"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          options={[
            { value: '', label: `${t('expense.category')}: ${t('common.all')}` },
            ...EXPENSE_CATEGORIES.map((c) => ({ value: c, label: t(`expenseCategory.${c}`) })),
          ]}
        />
      </div>

      <ErrorBox error={expenses.error} onRetry={expenses.reload} />

      <Card padded={false}>
        {!expenses.loading && expenses.items.length > 0 && (
          <div className="flex items-center justify-between border-b border-line px-4 py-2 text-sm">
            <span className="text-muted">{t('expense.total')}</span>
            <span className="tabular font-semibold text-ink">{formatMoney(expenses.total)}</span>
          </div>
        )}
        {expenses.loading && expenses.items.length === 0 ? (
          <Loading />
        ) : expenses.items.length === 0 ? (
          <EmptyState icon="wallet" title={t('expense.empty')} />
        ) : (
          <ul className="divide-y divide-line">
            {expenses.items.map((expense) => (
              <li key={expense.id} className="flex items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 text-sm font-medium text-ink">
                    {t(`expenseCategory.${expense.category}`)}
                    {expense.is_recurring && <Badge tone="good">{t('recurring.auto')}</Badge>}
                  </p>
                  <p className="truncate text-xs text-muted">
                    {formatDate(expense.date, lang)}
                    {expense.description && ` · ${expense.description}`}
                    {expense.created_by_name && ` · ${expense.created_by_name}`}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <span className="tabular mr-2 text-sm font-semibold text-ink">{formatMoney(expense.amount)}</span>
                  {isOwner && (
                    <>
                      <button
                        onClick={() => setEditing(expense)}
                        className="rounded-lg p-2 text-ink-2 hover:bg-soft hover:text-ink"
                        aria-label={t('common.edit')}
                        title={t('common.edit')}
                      >
                        <Icon name="edit" size={18} />
                      </button>
                      <button
                        onClick={() => remove(expense)}
                        className="rounded-lg p-2 text-ink-2 hover:bg-bad-soft hover:text-bad"
                        aria-label={t('common.delete')}
                        title={t('common.delete')}
                      >
                        <Icon name="trash" size={18} />
                      </button>
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {expenses.hasMore && (
        <div className="mt-4 text-center">
          <Button variant="secondary" loading={expenses.loading} onClick={expenses.loadMore}>
            {t('common.loadMore')}
          </Button>
        </div>
      )}

      {showRecurring && (
        <RecurringExpensesModal
          onClose={() => setShowRecurring(false)}
          onChanged={() => {
            expenses.reload()
            notifications.refresh()
          }}
        />
      )}

      {editing && (
        <ExpenseFormModal
          expense={editing}
          onClose={closeForm}
          onSaved={() => {
            closeForm()
            expenses.reload()
          }}
        />
      )}
    </>
  )
}
