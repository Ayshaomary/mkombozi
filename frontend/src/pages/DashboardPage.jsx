import { useState } from 'react'
import { Link } from 'react-router-dom'
import BarChart from '../components/BarChart'
import Icon from '../components/Icon'
import { Badge, Card, EmptyState, ErrorBox, Loading, PageHeader, StatTile } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { formatDate, formatDateTime, formatMoney, formatQuantity, formatWeekday, todayISO } from '../lib/format'
import { useApi } from '../lib/useApi'

function QuickAction({ to, icon, label }) {
  return (
    <Link
      to={to}
      className="flex items-center gap-3 rounded-xl border border-line bg-card px-4 py-3 text-sm font-medium text-ink hover:border-brand hover:bg-brand-soft"
    >
      <span className="rounded-lg bg-brand-soft p-2 text-brand-ink">
        <Icon name={icon} size={18} />
      </span>
      {label}
    </Link>
  )
}

export default function DashboardPage() {
  const { t, lang } = useLanguage()
  const { user } = useAuth()
  const { data, loading, error, reload } = useApi('/reports/dashboard/')
  const [today] = useState(todayISO)

  if (loading && !data) return <Loading />
  if (error) return <ErrorBox error={error} onRetry={reload} />

  const { today: todayTotals, month, last_7_days: week, stock, recent_sales: recent } = data
  const netProfit = Number(month.net_profit)

  return (
    <>
      <PageHeader title={t('dashboard.greeting', { name: user.first_name })} subtitle={formatDate(today, lang)} />

      <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <QuickAction to="/sell" icon="cart" label={t('dashboard.quickSell')} />
        <QuickAction to="/expenses?add=1" icon="wallet" label={t('dashboard.quickExpense')} />
        <QuickAction to="/products?add=1" icon="box" label={t('dashboard.quickProduct')} />
      </div>

      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label={t('dashboard.todaySales')}
          value={formatMoney(todayTotals.revenue)}
          sub={t('dashboard.salesCount', { count: todayTotals.sales_count })}
        />
        <StatTile label={t('dashboard.todayProfit')} value={formatMoney(todayTotals.gross_profit)} />
        <StatTile
          label={t('dashboard.monthSales')}
          value={formatMoney(month.revenue)}
          sub={t('dashboard.salesCount', { count: month.sales_count })}
        />
        <StatTile
          label={t('dashboard.monthNetProfit')}
          value={formatMoney(month.net_profit)}
          sub={t('dashboard.afterExpenses', { amount: formatMoney(month.expenses) })}
          subTone={netProfit < 0 ? 'bad' : undefined}
        />
      </div>

      <div className="grid items-start gap-5 lg:grid-cols-3">
        <Card title={t('dashboard.last7Days')} className="lg:col-span-2">
          <BarChart
            ariaLabel={t('dashboard.last7Days')}
            formatValue={formatMoney}
            data={week.map((d) => ({
              key: d.date,
              label: formatWeekday(d.date, lang),
              tooltipLabel: formatDate(d.date, lang),
              value: Number(d.revenue),
            }))}
          />
        </Card>

        <Card
          title={t('dashboard.lowStock')}
          action={stock.low_stock_count > 0 && <Badge tone="warn">{stock.low_stock_count}</Badge>}
        >
          {stock.low_stock.length === 0 ? (
            <EmptyState icon="check" title={t('dashboard.allStocked')} />
          ) : (
            <ul className="divide-y divide-line">
              {stock.low_stock.map((p) => (
                <li key={p.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <span className="truncate text-ink">{p.name}</span>
                  <span className={`shrink-0 ${Number(p.stock_quantity) <= 0 ? 'text-bad' : 'text-ink-2'}`}>
                    {t('dashboard.left', { qty: formatQuantity(p.stock_quantity) })}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <Link to="/products?low_stock=1" className="mt-3 inline-block text-sm font-medium text-brand-ink underline">
            {t('dashboard.seeAll')}
          </Link>
        </Card>

        <Card
          title={t('dashboard.recentSales')}
          className="lg:col-span-2"
          padded={false}
          action={
            <Link to="/sales" className="text-sm font-medium text-brand-ink underline">
              {t('dashboard.seeAll')}
            </Link>
          }
        >
          {recent.length === 0 ? (
            <EmptyState icon="receipt" title={t('dashboard.noSales')} />
          ) : (
            <ul className="divide-y divide-line">
              {recent.map((sale) => (
                <li key={sale.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                  <div className="min-w-0">
                    <p className="font-medium text-ink">
                      {sale.receipt_number} · {t(`payment.${sale.payment_method}`)}
                    </p>
                    <p className="truncate text-xs text-muted">
                      {formatDateTime(sale.sold_at, lang)} · {sale.customer_name || t('sales.walkIn')}
                    </p>
                  </div>
                  <span className="tabular shrink-0 font-semibold text-ink">{formatMoney(sale.total_amount)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <StatTile
          label={t('dashboard.stockValue')}
          value={formatMoney(stock.stock_cost_value)}
          sub={t('dashboard.stockValueHint', { count: stock.product_count })}
        />
      </div>
    </>
  )
}
