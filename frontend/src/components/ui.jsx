import { useEffect, useId } from 'react'
import { useLanguage } from '../i18n/LanguageContext'
import Icon from './Icon'

const BUTTON_VARIANTS = {
  primary: 'bg-brand text-white hover:bg-brand-hover',
  secondary: 'bg-card text-ink border border-line-strong hover:bg-soft',
  danger: 'bg-card text-bad border border-line-strong hover:bg-bad-soft',
  ghost: 'text-ink-2 hover:bg-soft hover:text-ink',
}

const BUTTON_SIZES = {
  sm: 'h-8 px-3 text-sm gap-1.5',
  md: 'h-10 px-4 text-sm gap-2',
  lg: 'h-12 px-5 text-base gap-2',
}

export function Button({ variant = 'primary', size = 'md', icon, loading, className = '', children, ...props }) {
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center rounded-lg font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-50 ${BUTTON_VARIANTS[variant]} ${BUTTON_SIZES[size]} ${className}`}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading ? <Spinner size={16} /> : icon && <Icon name={icon} size={size === 'sm' ? 16 : 18} />}
      {children}
    </button>
  )
}

const fieldBase =
  'w-full rounded-lg border bg-card px-3 text-sm text-ink placeholder:text-muted focus:outline-2 focus:outline-offset-0 focus:outline-brand'
const fieldClass = `${fieldBase} h-10`

function FieldWrapper({ id, label, error, hint, children, className = '' }) {
  return (
    <div className={className}>
      {label && (
        <label htmlFor={id} className="mb-1 block text-sm font-medium text-ink-2">
          {label}
        </label>
      )}
      {children}
      {error ? (
        <p className="mt-1 text-sm text-bad">{error}</p>
      ) : (
        hint && <p className="mt-1 text-xs text-muted">{hint}</p>
      )}
    </div>
  )
}

export function Input({ label, error, hint, className, ...props }) {
  const id = useId()
  return (
    <FieldWrapper id={id} label={label} error={error} hint={hint} className={className}>
      <input
        id={id}
        className={`${fieldClass} ${error ? 'border-bad' : 'border-line-strong'}`}
        aria-invalid={Boolean(error)}
        {...props}
      />
    </FieldWrapper>
  )
}

export function TextArea({ label, error, hint, className, rows = 3, ...props }) {
  const id = useId()
  return (
    <FieldWrapper id={id} label={label} error={error} hint={hint} className={className}>
      <textarea
        id={id}
        rows={rows}
        className={`${fieldBase} py-2 ${error ? 'border-bad' : 'border-line-strong'}`}
        aria-invalid={Boolean(error)}
        {...props}
      />
    </FieldWrapper>
  )
}

// Same rule as accounts/utils.py on the server: 10 digits without a country code (0712 345 678),
// 12 with Tanzania's (+255 712 345 678), 15 with any other (the international maximum)
function phoneDigitLimit(value) {
  const start = value.replace(/[\s\-()]/g, '')
  if (/^\+?255/.test(start)) return 12
  return start.startsWith('+') ? 15 : 10
}

// Keeps digits up to the limit, spaces and dashes, and a "+" only at the start
function limitPhone(value) {
  const maxDigits = phoneDigitLimit(value)
  let digits = 0
  let result = ''
  for (const char of value) {
    if (/\d/.test(char)) {
      if (digits === maxDigits) continue
      digits += 1
    } else if (!(char === '+' && result.trim() === '') && !/[\s\-()]/.test(char)) {
      continue
    }
    result += char
  }
  return result
}

export function PhoneInput({ onChange, ...props }) {
  return (
    <Input
      type="tel"
      inputMode="tel"
      {...props}
      onChange={(e) => {
        e.target.value = limitPhone(e.target.value)
        onChange(e)
      }}
    />
  )
}

export function Select({ label, error, hint, options, className, ...props }) {
  const id = useId()
  return (
    <FieldWrapper id={id} label={label} error={error} hint={hint} className={className}>
      <select id={id} className={`${fieldClass} ${error ? 'border-bad' : 'border-line-strong'}`} {...props}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </FieldWrapper>
  )
}

export function Checkbox({ label, ...props }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm text-ink-2">
      <input type="checkbox" className="size-4 accent-brand" {...props} />
      {label}
    </label>
  )
}

export function Card({ title, action, children, className = '', padded = true }) {
  return (
    <section className={`rounded-xl border border-line bg-card ${className}`}>
      {(title || action) && (
        <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold text-ink">{title}</h2>
          {action}
        </div>
      )}
      <div className={padded ? 'p-4' : ''}>{children}</div>
    </section>
  )
}

export function Modal({ open, onClose, title, children, footer, wide = false }) {
  useEffect(() => {
    if (!open) return
    const onKey = (event) => event.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-4">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`relative flex max-h-[92vh] w-full flex-col rounded-t-2xl bg-card shadow-xl sm:rounded-2xl ${wide ? 'sm:max-w-2xl' : 'sm:max-w-md'}`}
      >
        <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
          <h2 className="text-base font-semibold text-ink">{title}</h2>
          <button onClick={onClose} className="rounded-lg p-1 text-muted hover:bg-soft hover:text-ink" aria-label="Close">
            <Icon name="x" />
          </button>
        </div>
        <div className="overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>}
      </div>
    </div>
  )
}

const BADGE_TONES = {
  neutral: 'bg-soft text-ink-2',
  good: 'bg-brand-soft text-brand-ink',
  warn: 'bg-warn-soft text-warn-ink',
  bad: 'bg-bad-soft text-bad',
}

export function Badge({ tone = 'neutral', children }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${BADGE_TONES[tone]}`}>
      {children}
    </span>
  )
}

export function Spinner({ size = 20 }) {
  return (
    <span
      className="inline-block animate-spin rounded-full border-2 border-current border-t-transparent"
      style={{ width: size, height: size }}
      role="status"
    />
  )
}

export function Loading() {
  const { t } = useLanguage()
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-muted">
      <Spinner /> <span className="text-sm">{t('common.loading')}</span>
    </div>
  )
}

export function EmptyState({ icon = 'box', title, children }) {
  return (
    <div className="flex flex-col items-center gap-3 px-4 py-12 text-center">
      <div className="rounded-full bg-soft p-3 text-muted">
        <Icon name={icon} size={24} />
      </div>
      <p className="text-sm text-ink-2">{title}</p>
      {children}
    </div>
  )
}

function errorText(error, t) {
  if (!error) return ''
  if (error.status === 0) return t('common.networkError')
  return error.message
}

export function ErrorBox({ error, onRetry }) {
  const { t } = useLanguage()
  if (!error) return null
  return (
    <div role="alert" className="flex items-start gap-3 rounded-lg border border-bad/30 bg-bad-soft px-4 py-3 text-sm text-bad">
      <Icon name="alert" size={18} className="mt-0.5 shrink-0" />
      <p className="flex-1">{errorText(error, t)}</p>
      {onRetry && (
        <button onClick={onRetry} className="font-medium underline">
          {t('common.tryAgain')}
        </button>
      )}
    </div>
  )
}

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold text-ink sm:text-2xl">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-ink-2">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}

export function StatTile({ label, value, sub, subTone }) {
  const subColor = subTone === 'good' ? 'text-good' : subTone === 'bad' ? 'text-bad' : 'text-muted'
  return (
    <div className="rounded-xl border border-line bg-card p-4">
      <p className="text-sm text-ink-2">{label}</p>
      <p className="mt-1 text-xl font-semibold text-ink sm:text-2xl">{value}</p>
      {sub && <p className={`mt-1 text-xs ${subColor}`}>{sub}</p>}
    </div>
  )
}

export function SegmentedControl({ value, onChange, options, label }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex flex-wrap gap-1 rounded-lg bg-soft p-1">
      {options.map((option) => (
        <button
          key={option.value}
          role="radio"
          aria-checked={value === option.value}
          onClick={() => onChange(option.value)}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            value === option.value ? 'bg-card text-ink shadow-sm' : 'text-ink-2 hover:text-ink'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

export function PeriodFilter({ value, onChange, includeAll = false }) {
  const { t } = useLanguage()
  const periods = ['today', 'week', 'month', 'year', ...(includeAll ? ['all'] : [])]
  return (
    <SegmentedControl
      value={value}
      onChange={onChange}
      label={t('common.date')}
      options={periods.map((p) => ({ value: p, label: t(`period.${p}`) }))}
    />
  )
}

// The Save button of a form, with "Saved" or the error next to it (see lib/useSaveForm.js)
export function SaveRow({ saving, saved, error }) {
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
