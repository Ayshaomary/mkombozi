import { useState } from 'react'
import BarChart from '../components/BarChart'
import { Card, EmptyState, ErrorBox, Input, Loading, PageHeader, SegmentedControl } from '../components/ui'
import { useLanguage } from '../i18n/LanguageContext'
import { formatDate, formatMoney, formatQuantity, todayISO } from '../lib/format'
import { useApi } from '../lib/useApi'

const PERIODS = ['today', 'week', 'month', 'year', 'custom']

// Long ranges (more than ~2 months) are easier to read per month than per day
function chartRows(daily, lang) {
  if (daily.length <= 62) {
    return daily.map((d) => ({
      key: d.date,
      label: new Date(`${d.date}T00:00:00`).getDate().toString(),
      tooltipLabel: formatDate(d.date, lang),
      value: Number(d.revenue),
    }))
  }
  const months = new Map()
  for (const d of daily) {
    const key = d.date.slice(0, 7)
    months.set(key, (months.get(key) ?? 0) + Number(d.revenue))
  }
  const locale = lang === 'sw' ? 'sw-TZ' : 'en-GB'
  return [...months].map(([key, value]) => {
    const date = new Date(`${key}-01T00:00:00`)
    return {
      key,
      label: date.toLocaleDateString(locale, { month: 'short' }),
      tooltipLabel: date.toLocaleDateString(locale, { month: 'long', year: 'numeric' }),
      value,
    }
  })
}

function StatementRow({ label, value, hint, strong, negative }) {
  return (
    <div className={`flex items-start justify-between gap-4 py-2.5 ${strong ? 'border-t border-line-strong' : ''}`}>
      <div>
        <p className={strong ? 'font-semibold text-ink' : 'text-ink-2'}>{label}</p>
        {hint && <p className="text-xs text-muted">{hint}</p>}
      </div>
      <p className={`tabular shrink-0 ${strong ? 'text-lg font-bold' : ''} ${negative ? 'text-bad' : 'text-ink'}`}>
        {formatMoney(value)}
      </p>
    </div>
  )
}

function SimpleTable({ columns, rows, empty }) {
  if (rows.length === 0) return <EmptyState icon="chart" title={empty} />
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs text-muted">
            {columns.map((c) => (
              <th key={c.key} className={`px-4 py-2 font-medium ${c.numeric ? 'text-right' : ''}`}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((row, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c.key} className={`px-4 py-2 ${c.numeric ? 'tabular text-right' : 'text-ink'}`}>
                  {c.render ? c.render(row) : row[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function ReportsPage() {
  const { t, lang } = useLanguage()
  const [period, setPeriod] = useState('month')
  const [range, setRange] = useState({ start: todayISO().slice(0, 8) + '01', end: todayISO() })
  const [showTable, setShowTable] = useState(false)

  const params = period === 'custom' ? range : { period }
  const { data, loading, error, reload } = useApi('/reports/summary/', params)

  const rows = data ? chartRows(data.daily, lang) : []
  const monthly = data && data.daily.length > 62
  const net = data ? Number(data.totals.net_profit) : 0

  return (
    <>
      <PageHeader
        title={t('reports.title')}
        subtitle={data && `${formatDate(data.start, lang)} – ${formatDate(data.end, lang)}`}
      />

      <div className="mb-5 flex flex-wrap items-end gap-3">
        <SegmentedControl
          value={period}
          onChange={setPeriod}
          label={t('common.date')}
          options={PERIODS.map((p) => ({ value: p, label: t(`period.${p}`) }))}
        />
        {period === 'custom' && (
          <div className="flex flex-wrap gap-3">
            <Input
              label={t('period.from')}
              type="date"
              value={range.start}
              max={range.end}
              onChange={(e) => e.target.value && setRange({ ...range, start: e.target.value })}
            />
            <Input
              label={t('period.to')}
              type="date"
              value={range.end}
              min={range.start}
              onChange={(e) => e.target.value && setRange({ ...range, end: e.target.value })}
            />
          </div>
        )}
      </div>

      <ErrorBox error={error} onRetry={reload} />
      {loading && !data && <Loading />}

      {data && (
        <div className={`grid items-start gap-5 lg:grid-cols-5 ${loading ? 'opacity-60' : ''}`}>
          <Card title={t('reports.profitLoss')} className="lg:col-span-2">
            <div className="text-sm">
              <StatementRow label={t('reports.revenue')} value={data.totals.revenue} />
              <StatementRow label={`− ${t('reports.costOfGoods')}`} value={data.totals.cost_of_goods} />
              <StatementRow
                label={t('reports.grossProfit')}
                hint={t('reports.explainGross')}
                value={data.totals.gross_profit}
                strong
                negative={Number(data.totals.gross_profit) < 0}
              />
              <StatementRow label={`− ${t('reports.expenses')}`} value={data.totals.expenses} />
              <StatementRow
                label={net < 0 ? t('reports.netLoss') : t('reports.netProfit')}
                hint={t('reports.explainNet')}
                value={data.totals.net_profit}
                strong
                negative={net < 0}
              />
              <div className="mt-3 space-y-1 border-t border-line pt-3 text-xs text-muted">
                <p className="flex justify-between">
                  <span>{t('reports.salesCount')}</span>
                  <span className="tabular">{data.totals.sales_count}</span>
                </p>
                <p className="flex justify-between">
                  <span>{t('reports.discounts')}</span>
                  <span className="tabular">{formatMoney(data.totals.discounts)}</span>
                </p>
              </div>
            </div>
          </Card>

          <Card
            title={monthly ? t('reports.monthlySales') : t('reports.dailySales')}
            className="lg:col-span-3"
            action={
              <button onClick={() => setShowTable(!showTable)} className="text-sm font-medium text-brand-ink underline">
                {showTable ? t('reports.hideTable') : t('reports.showTable')}
              </button>
            }
          >
            {showTable ? (
              <div className="max-h-72 overflow-y-auto">
                <SimpleTable
                  empty={t('reports.noData')}
                  rows={rows}
                  columns={[
                    { key: 'tooltipLabel', label: t('reports.day') },
                    { key: 'value', label: t('reports.revenue'), numeric: true, render: (r) => formatMoney(r.value) },
                  ]}
                />
              </div>
            ) : (
              <BarChart
                data={rows}
                formatValue={formatMoney}
                ariaLabel={monthly ? t('reports.monthlySales') : t('reports.dailySales')}
              />
            )}
          </Card>

          <Card title={t('reports.topProducts')} className="lg:col-span-3" padded={false}>
            <SimpleTable
              empty={t('reports.noData')}
              rows={data.top_products}
              columns={[
                { key: 'product_name', label: t('product.name') },
                { key: 'quantity_sold', label: t('reports.qtySold'), numeric: true, render: (r) => formatQuantity(r.quantity_sold) },
                { key: 'revenue', label: t('reports.revenue'), numeric: true, render: (r) => formatMoney(r.revenue) },
                {
                  key: 'profit',
                  label: t('sales.profit'),
                  numeric: true,
                  render: (r) => <span className={Number(r.profit) < 0 ? 'text-bad' : 'text-good'}>{formatMoney(r.profit)}</span>,
                },
              ]}
            />
          </Card>

          <div className="space-y-5 lg:col-span-2">
            <Card title={t('reports.paymentMethods')} padded={false}>
              <SimpleTable
                empty={t('reports.noData')}
                rows={data.payment_methods}
                columns={[
                  { key: 'payment_method', label: t('pos.paymentMethod'), render: (r) => t(`payment.${r.payment_method}`) },
                  { key: 'count', label: '#', numeric: true },
                  { key: 'total', label: t('common.total'), numeric: true, render: (r) => formatMoney(r.total) },
                ]}
              />
            </Card>
            <Card title={t('reports.expensesByCategory')} padded={false}>
              <SimpleTable
                empty={t('reports.noData')}
                rows={data.expenses_by_category}
                columns={[
                  { key: 'category', label: t('expense.category'), render: (r) => t(`expenseCategory.${r.category}`) },
                  { key: 'total', label: t('common.total'), numeric: true, render: (r) => formatMoney(r.total) },
                ]}
              />
            </Card>
          </div>
        </div>
      )}
    </>
  )
}
