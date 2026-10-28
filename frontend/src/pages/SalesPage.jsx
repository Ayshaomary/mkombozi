import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Icon from '../components/Icon'
import { Button, Card, EmptyState, ErrorBox, Loading, Modal, PageHeader, PeriodFilter, Select } from '../components/ui'
import PrintButton from '../components/PrintButton'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { api } from '../lib/api'
import { PAYMENT_METHODS } from '../lib/constants'
import { formatDateTime, formatMoney, formatQuantity } from '../lib/format'
import { fetchAll, useApi, usePaginated } from '../lib/useApi'
import { useDebounce } from '../lib/useDebounce'

function SaleDetails({ saleId, onClose, onCancelled }) {
  const { t, lang } = useLanguage()
  const { can } = useAuth()
  const { data: sale, loading, error } = useApi(`/sales/${saleId}/`)
  const [cancelError, setCancelError] = useState(null)
  const [cancelling, setCancelling] = useState(false)

  const cancelSale = async () => {
    if (!window.confirm(t('sales.cancelConfirm'))) return
    setCancelling(true)
    try {
      await api.delete(`/sales/${saleId}/`)
      onCancelled()
    } catch (err) {
      setCancelError(err)
      setCancelling(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={sale ? `${t('pos.receipt')} ${sale.receipt_number}` : t('sales.details')}
      footer={
        can('manage') &&
        sale && (
          <Button variant="danger" icon="trash" loading={cancelling} onClick={cancelSale}>
            {t('sales.cancelSale')}
          </Button>
        )
      }
    >
      {loading && <Loading />}
      <ErrorBox error={error || cancelError} />
      {sale && (
        <div className="space-y-3 text-sm">
          <dl className="grid grid-cols-2 gap-2 text-ink-2">
            <dt>{t('common.date')}</dt>
            <dd className="text-right text-ink">{formatDateTime(sale.sold_at, lang)}</dd>
            <dt>{t('pos.paymentMethod')}</dt>
            <dd className="text-right text-ink">{t(`payment.${sale.payment_method}`)}</dd>
            <dt>{t('sales.customer')}</dt>
            <dd className="text-right text-ink">
              {sale.customer_name || t('sales.walkIn')}
              {sale.customer_phone && <span className="block text-xs text-muted">{sale.customer_phone}</span>}
            </dd>
            {sale.created_by_name && (
              <>
                <dt>{t('sales.soldBy')}</dt>
                <dd className="text-right text-ink">{sale.created_by_name}</dd>
              </>
            )}
          </dl>
          <ul className="divide-y divide-line border-y border-line">
            {sale.items.map((item) => (
              <li key={item.id} className="flex justify-between gap-3 py-2">
                <span className="text-ink">
                  {item.product_name}
                  <span className="block text-xs text-muted">
                    {formatQuantity(item.quantity)} × {formatMoney(item.unit_price)}
                  </span>
                </span>
                <span className="tabular text-ink">{formatMoney(item.subtotal)}</span>
              </li>
            ))}
          </ul>
          {Number(sale.discount) > 0 && (
            <p className="flex justify-between text-ink-2">
              <span>{t('pos.discount')}</span>
              <span className="tabular">-{formatMoney(sale.discount)}</span>
            </p>
          )}
          <p className="flex justify-between text-base font-bold text-ink">
            <span>{t('common.total')}</span>
            <span className="tabular">{formatMoney(sale.total_amount)}</span>
          </p>
          {can('reports') && (
            <p className="flex justify-between text-ink-2">
              <span>{t('sales.profit')}</span>
              <span className={`tabular font-semibold ${Number(sale.profit) < 0 ? 'text-bad' : 'text-good'}`}>
                {formatMoney(sale.profit)}
              </span>
            </p>
          )}
          {sale.note && <p className="text-ink-2">{sale.note}</p>}
        </div>
      )}
    </Modal>
  )
}

export default function SalesPage() {
  const { t, lang } = useLanguage()
  const { can } = useAuth()
  const navigate = useNavigate()
  const [period, setPeriod] = useState('today')
  const [paymentMethod, setPaymentMethod] = useState('')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState(null)
  const debouncedSearch = useDebounce(search)

  const listParams = {
    period: period === 'all' ? '' : period,
    payment_method: paymentMethod,
    search: debouncedSearch,
  }
  const sales = usePaginated('/sales/', listParams)

  return (
    <>
      <PageHeader
        title={t('sales.title')}
        actions={
          <>
            <PrintButton
              title={t('sales.title')}
              subtitle={[t(`period.${period}`), paymentMethod && t(`payment.${paymentMethod}`), debouncedSearch && `"${debouncedSearch}"`]
                .filter(Boolean)
                .join(' · ')}
              load={() => fetchAll('/sales/', listParams)}
              columns={[
                { label: t('sales.receiptNo'), value: (s) => s.receipt_number },
                { label: t('common.date'), value: (s) => formatDateTime(s.sold_at, lang) },
                { label: t('sales.customer'), value: (s) => s.customer_name || t('sales.walkIn') },
                { label: t('pos.paymentMethod'), value: (s) => t(`payment.${s.payment_method}`) },
                { label: t('sales.items'), value: (s) => s.item_count, align: 'right' },
                { label: t('common.total'), value: (s) => formatMoney(s.total_amount), align: 'right' },
                ...(can('reports')
                  ? [{ label: t('sales.profit'), value: (s) => formatMoney(s.profit), align: 'right' }]
                  : []),
              ]}
              footer={(rows, total) => [
                [t('print.totalSales'), formatMoney(total)],
                ...(can('reports')
                  ? [[t('sales.profit'), formatMoney(rows.reduce((sum, s) => sum + Number(s.profit), 0))]]
                  : []),
              ]}
            />
            {can('sales') && (
              <Button icon="plus" onClick={() => navigate('/sell')}>
                {t('nav.newSale')}
              </Button>
            )}
          </>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <PeriodFilter value={period} onChange={setPeriod} includeAll />
        <Select
          aria-label={t('pos.paymentMethod')}
          className="w-48"
          value={paymentMethod}
          onChange={(e) => setPaymentMethod(e.target.value)}
          options={[
            { value: '', label: `${t('pos.paymentMethod')}: ${t('common.all')}` },
            ...PAYMENT_METHODS.map((m) => ({ value: m, label: t(`payment.${m}`) })),
          ]}
        />
        <div className="relative min-w-0 flex-1 basis-48">
          <Icon name="search" size={18} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('sales.searchPlaceholder')}
            aria-label={t('sales.searchPlaceholder')}
            className="h-10 w-full rounded-lg border border-line-strong bg-card pr-3 pl-10 text-sm text-ink placeholder:text-muted focus:outline-2 focus:outline-brand"
          />
        </div>
      </div>

      <ErrorBox error={sales.error} onRetry={sales.reload} />

      <Card padded={false}>
        {!sales.loading && sales.items.length > 0 && (
          <div className="flex items-center justify-between border-b border-line px-4 py-2 text-sm">
            <span className="text-muted">{t('sales.count', { count: sales.count })}</span>
            <span className="tabular font-semibold text-ink">
              {t('common.total')}: {formatMoney(sales.total)}
            </span>
          </div>
        )}
        {sales.loading && sales.items.length === 0 ? (
          <Loading />
        ) : sales.items.length === 0 ? (
          <EmptyState icon="receipt" title={t('sales.empty')} />
        ) : (
          <ul className="divide-y divide-line">
            {sales.items.map((sale) => (
              <li key={sale.id}>
                <button
                  onClick={() => setSelected(sale.id)}
                  className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-soft"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-ink">
                      {sale.receipt_number} · {t(`payment.${sale.payment_method}`)}
                    </p>
                    <p className="truncate text-xs text-muted">
                      {formatDateTime(sale.sold_at, lang)} · {sale.customer_name || t('sales.walkIn')} ·{' '}
                      {t('pos.items', { count: sale.item_count })}
                      {sale.created_by_name && ` · ${sale.created_by_name}`}
                    </p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="tabular text-sm font-semibold text-ink">{formatMoney(sale.total_amount)}</p>
                    {can('reports') && (
                      <p className={`tabular text-xs ${Number(sale.profit) < 0 ? 'text-bad' : 'text-good'}`}>
                        {t('sales.profit')}: {formatMoney(sale.profit)}
                      </p>
                    )}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {sales.hasMore && (
        <div className="mt-4 text-center">
          <Button variant="secondary" loading={sales.loading} onClick={sales.loadMore}>
            {t('common.loadMore')}
          </Button>
        </div>
      )}

      {selected && (
        <SaleDetails
          saleId={selected}
          onClose={() => setSelected(null)}
          onCancelled={() => {
            setSelected(null)
            sales.reload()
          }}
        />
      )}
    </>
  )
}
