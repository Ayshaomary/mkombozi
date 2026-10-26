import { useState } from 'react'
import Icon from '../components/Icon'
import { Badge, Button, Card, EmptyState, ErrorBox, Input, Loading, Modal, PageHeader, Select } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { api } from '../lib/api'
import { SUBSCRIPTION_PROVIDERS } from '../lib/constants'
import { formatDate, formatMoney } from '../lib/format'
import { useApi } from '../lib/useApi'

const PAYMENT_TONES = { pending: 'warn', completed: 'good', failed: 'bad' }

function PayModal({ plan, onClose, onDone }) {
  const { t } = useLanguage()
  const { user } = useAuth()
  const [form, setForm] = useState({ provider: 'mpesa', phone: user.phone })
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [payment, setPayment] = useState(null)

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      setPayment(await api.post('/subscription/payments/', { plan: plan.id, ...form }))
      onDone()
    } catch (err) {
      setError(err)
    } finally {
      setSaving(false)
    }
  }

  if (payment) {
    return (
      <Modal open onClose={onClose} title={t('subscription.pendingTitle')} footer={<Button onClick={onClose}>{t('common.close')}</Button>}>
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="rounded-full bg-brand-soft p-3 text-brand-ink">
            <Icon name="check" size={28} />
          </div>
          <p className="text-sm text-ink-2">{t('subscription.pendingText', { ref: payment.reference })}</p>
        </div>
      </Modal>
    )
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={t('subscription.payTitle', { plan: plan.name })}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form="pay-form" loading={saving}>
            {t('subscription.confirmPay')}
          </Button>
        </>
      }
    >
      <form id="pay-form" onSubmit={submit} className="space-y-4">
        <p className="text-2xl font-bold text-ink">{formatMoney(plan.price)}</p>
        <ErrorBox error={error} />
        <Select
          label={t('subscription.provider')}
          value={form.provider}
          onChange={(e) => setForm({ ...form, provider: e.target.value })}
          options={SUBSCRIPTION_PROVIDERS.map((p) => ({ value: p, label: t(`payment.${p}`) }))}
        />
        <Input
          label={t('subscription.payPhone')}
          type="tel"
          inputMode="tel"
          value={form.phone}
          onChange={(e) => setForm({ ...form, phone: e.target.value })}
          error={error?.fields?.phone}
          required
        />
      </form>
    </Modal>
  )
}

export default function SubscriptionPage() {
  const { t, lang } = useLanguage()
  const { subscription, isOwner, loadSubscription } = useAuth()
  const plans = useApi('/subscription/plans/')
  const payments = useApi('/subscription/payments/')
  const [payingFor, setPayingFor] = useState(null)

  if (!subscription) return <Loading />

  const status = subscription.is_valid ? subscription.status : 'expired'
  const statusTone = status === 'expired' || status === 'cancelled' ? 'bad' : status === 'trial' ? 'warn' : 'good'

  return (
    <>
      <PageHeader title={t('subscription.title')} />

      <Card className="mb-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-sm text-ink-2">{t('subscription.status')}</p>
            <p className="mt-1 flex items-center gap-2 text-lg font-semibold text-ink">
              <Badge tone={statusTone}>{t(`subscription.${status}`)}</Badge>
              {subscription.plan && <span>{subscription.plan.name}</span>}
            </p>
            <p className="mt-1 text-sm text-muted">
              {subscription.is_valid
                ? t('subscription.endsOn', { date: formatDate(subscription.current_period_end, lang) })
                : t('subscription.endedOn', { date: formatDate(subscription.current_period_end, lang) })}
            </p>
          </div>
          {subscription.is_valid && (
            <p className="text-3xl font-bold text-ink">{t('subscription.daysLeft', { days: subscription.days_left })}</p>
          )}
        </div>
      </Card>

      <h2 className="mb-3 text-base font-semibold text-ink">{t('subscription.choosePlan')}</h2>
      {!isOwner && <p className="mb-3 text-sm text-ink-2">{t('subscription.ownerOnly')}</p>}
      <ErrorBox error={plans.error} onRetry={plans.reload} />
      {plans.loading && <Loading />}
      <div className="mb-6 grid gap-3 sm:grid-cols-3">
        {plans.data?.map((plan) => (
          <div key={plan.id} className="flex flex-col rounded-xl border border-line bg-card p-4">
            <p className="font-semibold text-ink">{plan.name}</p>
            <p className="mt-2 text-2xl font-bold text-ink">{formatMoney(plan.price)}</p>
            <p className="text-sm text-muted">{t('subscription.days', { days: plan.duration_days })}</p>
            {plan.description && <p className="mt-2 flex-1 text-sm text-ink-2">{plan.description}</p>}
            {isOwner && (
              <Button className="mt-4 w-full" onClick={() => setPayingFor(plan)}>
                {t('subscription.pay')}
              </Button>
            )}
          </div>
        ))}
      </div>

      <Card title={t('subscription.history')} padded={false}>
        {payments.loading && !payments.data ? (
          <Loading />
        ) : !payments.data?.results.length ? (
          <EmptyState icon="card" title={t('subscription.noPayments')} />
        ) : (
          <ul className="divide-y divide-line">
            {payments.data.results.map((p) => (
              <li key={p.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                <div className="min-w-0">
                  <p className="font-medium text-ink">{p.plan_name}</p>
                  <p className="truncate text-xs text-muted">
                    {formatDate(p.created_at, lang)} · {t(`payment.${p.provider}`)} · {t('subscription.reference')}: {p.reference}
                  </p>
                </div>
                <div className="shrink-0 text-right">
                  <p className="tabular font-semibold text-ink">{formatMoney(p.amount)}</p>
                  <Badge tone={PAYMENT_TONES[p.status]}>{t(`subscription.${p.status}`)}</Badge>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {payingFor && (
        <PayModal
          plan={payingFor}
          onClose={() => setPayingFor(null)}
          onDone={() => {
            payments.reload()
            loadSubscription()
          }}
        />
      )}
    </>
  )
}
