import { useCallback, useEffect, useState } from 'react'
import Icon from '../components/Icon'
import { Badge, Button, Card, EmptyState, ErrorBox, Loading, Modal, PageHeader, PhoneInput, Select, Spinner } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { api } from '../lib/api'
import { CONTROL_NUMBER_NETWORKS, NETWORK_PREFIXES, phonePrefix, SUBSCRIPTION_PROVIDERS } from '../lib/constants'
import { formatDate, formatMoney } from '../lib/format'
import { useApi } from '../lib/useApi'

const PAYMENT_TONES = { pending: 'warn', completed: 'good', failed: 'bad' }

// After the Push USSD is sent, check every few seconds whether the payer approved it on their phone
const CHECK_EVERY_MS = 5000
const STOP_CHECKING_AFTER_MS = 3 * 60 * 1000
// A control number can take a while: the payer has to open mobile money and type it in
const STOP_CHECKING_CONTROL_NUMBER_AFTER_MS = 15 * 60 * 1000

function PaymentResult({ title, icon, tone, text, onClose, action }) {
  const { t } = useLanguage()
  const tones = { good: 'bg-brand-soft text-brand-ink', bad: 'bg-bad-soft text-bad', wait: 'bg-warn-soft text-warn-ink' }
  return (
    <Modal
      open
      onClose={onClose}
      title={title}
      footer={
        <>
          {action}
          <Button variant={action ? 'secondary' : 'primary'} onClick={onClose}>
            {t('common.close')}
          </Button>
        </>
      }
    >
      <div className="flex flex-col items-center gap-3 text-center">
        <div className={`rounded-full p-3 ${tones[tone]}`}>{icon === 'spinner' ? <Spinner size={28} /> : <Icon name={icon} size={28} />}</div>
        <p className="text-sm text-ink-2">{text}</p>
      </div>
    </Modal>
  )
}

// Shows a control number, how to pay it on each network, and waits for the payment to arrive
function ControlNumberModal({ payment: initial, onClose, onDone }) {
  const { t } = useLanguage()
  const { subscription } = useAuth()
  const [payment, setPayment] = useState(initial)
  const [copied, setCopied] = useState(false)

  const pending = payment.status === 'pending'
  const paymentId = payment.id

  useEffect(() => {
    if (!pending) return
    const started = Date.now()
    const timer = setInterval(async () => {
      if (Date.now() - started > STOP_CHECKING_CONTROL_NUMBER_AFTER_MS) {
        clearInterval(timer)
        return
      }
      try {
        const latest = await api.get(`/subscription/payments/${paymentId}/`)
        if (latest.status !== 'pending') {
          setPayment(latest)
          onDone()
        }
      } catch {
        // A failed check is not a failed payment; try again on the next tick
      }
    }, CHECK_EVERY_MS)
    return () => clearInterval(timer)
  }, [pending, paymentId, onDone])

  if (payment.status === 'completed') {
    return (
      <PaymentResult
        title={t('subscription.paidTitle')}
        icon="check"
        tone="good"
        text={t('subscription.paidText', { plan: payment.plan_name })}
        onClose={onClose}
      />
    )
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(payment.control_number)
      setCopied(true)
    } catch {
      // Copying can be blocked by the browser; the number can still be selected by hand
    }
  }

  // M-Pesa's business number is the merchant's own, so its steps only show once it is set on the server
  const mpesaNumber = subscription?.control_numbers?.mpesa_business_number
  const networks = CONTROL_NUMBER_NETWORKS.map((n) => (n.provider === 'mpesa' ? { ...n, business: mpesaNumber } : n)).filter(
    (n) => n.business,
  )

  return (
    <Modal
      open
      onClose={onClose}
      title={t('subscription.controlNumberTitle')}
      footer={<Button onClick={onClose}>{t('common.close')}</Button>}
    >
      <div className="space-y-4">
        <div className="rounded-xl bg-brand-soft p-4 text-center">
          <p className="text-sm text-brand-ink">{t('subscription.controlNumber')}</p>
          <p className="tabular mt-1 text-3xl font-bold tracking-wider text-ink select-all">{payment.control_number}</p>
          <Button variant="secondary" size="sm" className="mt-3" icon={copied ? 'check' : undefined} onClick={copy}>
            {copied ? t('subscription.copied') : t('subscription.copy')}
          </Button>
        </div>
        <p className="text-sm text-ink-2">
          {t('subscription.controlNumberAmount', { amount: formatMoney(payment.amount) })}
        </p>
        <div>
          <h3 className="mb-2 text-sm font-semibold text-ink">{t('subscription.howToPay')}</h3>
          <ul className="space-y-2 text-sm text-ink-2">
            {networks.map((n) => (
              <li key={n.provider}>
                <span className="font-medium text-ink">{t(`payment.${n.provider}`)}:</span>{' '}
                {t('subscription.payStep', { dial: n.dial, menu: n.menu, business: n.business })}
              </li>
            ))}
            <li>
              <span className="font-medium text-ink">{t('subscription.crdb')}:</span> {t('subscription.payStepCrdb')}
            </li>
          </ul>
        </div>
        {pending && (
          <p className="flex items-center gap-2 text-xs text-muted">
            <Spinner size={14} />
            {t('subscription.waitingForPayment')}
          </p>
        )}
      </div>
    </Modal>
  )
}

function PayModal({ plan, onClose, onDone }) {
  const { t } = useLanguage()
  const { user, subscription } = useAuth()
  const [form, setForm] = useState({ provider: 'mpesa', phone: user.phone })
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [payment, setPayment] = useState(null)
  const [timedOut, setTimedOut] = useState(false)

  const waiting = Boolean(payment?.push_sent && payment.status === 'pending')
  const paymentId = payment?.id

  const providers = SUBSCRIPTION_PROVIDERS.filter((p) => p !== 'controlnumber' || subscription?.control_numbers?.enabled)
  const isControlNumber = form.provider === 'controlnumber'

  // The number must belong to the chosen network, e.g. M-Pesa: 074, 075, 076 or 079
  const prefixes = NETWORK_PREFIXES[form.provider]
  const prefixList = prefixes?.join(', ')
  const prefix = phonePrefix(form.phone)
  const wrongNetwork = Boolean(prefixes && prefix && !prefixes.includes(prefix))
  const phoneError = wrongNetwork
    ? t('subscription.wrongNetwork', { network: t(`payment.${form.provider}`), prefixes: prefixList })
    : error?.fields?.phone

  useEffect(() => {
    if (!waiting) return
    const started = Date.now()
    const timer = setInterval(async () => {
      if (Date.now() - started > STOP_CHECKING_AFTER_MS) {
        clearInterval(timer)
        setTimedOut(true)
        return
      }
      try {
        const latest = await api.get(`/subscription/payments/${paymentId}/`)
        if (latest.status !== 'pending') {
          setPayment(latest)
          onDone()
        }
      } catch {
        // A failed check is not a failed payment; try again on the next tick
      }
    }, CHECK_EVERY_MS)
    return () => clearInterval(timer)
  }, [waiting, paymentId, onDone])

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      setPayment(await api.post('/subscription/payments/', { plan: plan.id, ...form }))
    } catch (err) {
      setError(err)
    } finally {
      setSaving(false)
      onDone()
    }
  }

  const tryAgain = () => {
    setPayment(null)
    setTimedOut(false)
  }

  if (payment?.control_number) {
    return <ControlNumberModal payment={payment} onClose={onClose} onDone={onDone} />
  }

  if (payment?.status === 'completed') {
    return (
      <PaymentResult
        title={t('subscription.paidTitle')}
        icon="check"
        tone="good"
        text={t('subscription.paidText', { plan: plan.name })}
        onClose={onClose}
      />
    )
  }

  if (payment?.status === 'failed') {
    return (
      <PaymentResult
        title={t('subscription.failedTitle')}
        icon="alert"
        tone="bad"
        text={t('subscription.failedText')}
        onClose={onClose}
        action={<Button onClick={tryAgain}>{t('common.tryAgain')}</Button>}
      />
    )
  }

  if (waiting) {
    return (
      <PaymentResult
        title={t('subscription.checkPhoneTitle')}
        icon={timedOut ? 'history' : 'spinner'}
        tone="wait"
        text={
          timedOut
            ? t('subscription.stillWaitingText', { ref: payment.reference })
            : t('subscription.checkPhoneText', { phone: payment.phone, amount: formatMoney(payment.amount) })
        }
        onClose={onClose}
      />
    )
  }

  if (payment) {
    return (
      <PaymentResult
        title={t('subscription.pendingTitle')}
        icon="check"
        tone="good"
        text={t('subscription.pendingText', { ref: payment.reference })}
        onClose={onClose}
      />
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
          <Button type="submit" form="pay-form" loading={saving} disabled={wrongNetwork}>
            {isControlNumber ? t('subscription.getNumber') : t('subscription.confirmPay')}
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
          options={providers.map((p) => ({ value: p, label: t(`payment.${p}`) }))}
        />
        {isControlNumber ? (
          <p className="text-sm text-ink-2">{t('subscription.controlNumberHint')}</p>
        ) : (
          <PhoneInput
            label={t('subscription.payPhone')}
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            hint={prefixes && t('subscription.prefixHint', { network: t(`payment.${form.provider}`), prefixes: prefixList })}
            error={phoneError}
            required
          />
        )}
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
  const [showingNumber, setShowingNumber] = useState(null)
  const reloadPayments = payments.reload
  const handlePaymentChange = useCallback(() => {
    reloadPayments()
    loadSubscription()
  }, [reloadPayments, loadSubscription])

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
                    {formatDate(p.created_at, lang)} · {t(`payment.${p.provider}`)} ·{' '}
                    {p.control_number
                      ? `${t('subscription.controlNumber')}: ${p.control_number}`
                      : `${t('subscription.reference')}: ${p.reference}`}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  {p.control_number && p.status === 'pending' && (
                    <Button variant="secondary" size="sm" onClick={() => setShowingNumber(p)}>
                      {t('subscription.show')}
                    </Button>
                  )}
                  <div className="text-right">
                    <p className="tabular font-semibold text-ink">{formatMoney(p.amount)}</p>
                    <Badge tone={PAYMENT_TONES[p.status]}>{t(`subscription.${p.status}`)}</Badge>
                  </div>
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
          onDone={handlePaymentChange}
        />
      )}

      {showingNumber && (
        <ControlNumberModal
          payment={showingNumber}
          onClose={() => setShowingNumber(null)}
          onDone={handlePaymentChange}
        />
      )}
    </>
  )
}
