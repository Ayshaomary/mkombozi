import { useRef, useState } from 'react'
import Icon from '../components/Icon'
import Letterhead from '../components/Letterhead'
import { useNotifications } from '../components/Notifications'
import { Badge, Button, Card, EmptyState, ErrorBox, Input, Loading, Modal, PageHeader, PhoneInput, Select } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useOffline } from '../context/OfflineContext'
import { useLanguage } from '../i18n/LanguageContext'
import { api } from '../lib/api'
import { PAYMENT_METHODS } from '../lib/constants'
import { formatDateTime, formatMoney, formatQuantity } from '../lib/format'
import { useApi } from '../lib/useApi'
import { newClientId } from '../lib/outbox'
import { useDebounce } from '../lib/useDebounce'

function Receipt({ sale, onClose }) {
  const { t, lang } = useLanguage()
  const { user } = useAuth()
  return (
    <Modal
      open
      onClose={onClose}
      title={sale.offline ? t('pos.savedOffline') : t('pos.success')}
      footer={
        <>
          <Button variant="secondary" icon="printer" onClick={() => window.print()}>
            {t('pos.print')}
          </Button>
          <Button icon="plus" onClick={onClose}>
            {t('pos.another')}
          </Button>
        </>
      }
    >
      {sale.offline && (
        <p className="mb-4 flex items-start gap-2 rounded-lg bg-warn-soft p-3 text-sm text-warn-ink">
          <Icon name="repeat" size={16} className="mt-0.5 shrink-0" />
          {t('pos.savedOfflineText')}
        </p>
      )}
      <div className="print-area text-sm">
        <div className="mb-3 text-center">
          <Letterhead business={user.business} centered />
          <p className="mt-2 text-ink-2">
            {t('pos.receipt')} {sale.receipt_number} · {formatDateTime(sale.sold_at, lang)}
          </p>
        </div>
        <ul className="divide-y divide-dashed divide-line-strong border-y border-dashed border-line-strong">
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
          <p className="mt-2 flex justify-between text-ink-2">
            <span>{t('pos.discount')}</span>
            <span className="tabular">-{formatMoney(sale.discount)}</span>
          </p>
        )}
        <p className="mt-2 flex justify-between text-base font-bold text-ink">
          <span>{t('common.total')}</span>
          <span className="tabular">{formatMoney(sale.total_amount)}</span>
        </p>
        <p className="mt-1 text-ink-2">
          {t('pos.paymentMethod')}: {t(`payment.${sale.payment_method}`)}
        </p>
        {sale.customer_name && (
          <p className="text-ink-2">
            {t('sales.customer')}: {sale.customer_name}
          </p>
        )}
      </div>
    </Modal>
  )
}

export default function NewSalePage() {
  const { t } = useLanguage()
  const offline = useOffline()
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebounce(search)
  // Offline, only the full list saved last time is available, so search within it on the phone
  const products = useApi('/products/', {
    active: 'true',
    // Raw materials are used in production, not sold
    kind: 'goods',
    search: offline.online ? debouncedSearch : '',
    page_size: 100,
  })
  const [cart, setCart] = useState([])
  const [paymentMethod, setPaymentMethod] = useState('cash')
  const [discount, setDiscount] = useState('')
  const [showDetails, setShowDetails] = useState(false)
  const [customer, setCustomer] = useState({ customer_name: '', customer_phone: '', note: '' })
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [receipt, setReceipt] = useState(null)
  const cartRef = useRef(null)
  const notifications = useNotifications()

  const addToCart = (product) => {
    setError(null)
    setCart((current) => {
      const existing = current.find((line) => line.product.id === product.id)
      if (existing) {
        return current.map((line) =>
          line.product.id === product.id ? { ...line, quantity: String(Number(line.quantity) + 1) } : line,
        )
      }
      return [...current, { product, quantity: '1', unit_price: String(Number(product.selling_price)) }]
    })
  }

  const updateLine = (productId, changes) =>
    setCart((current) => current.map((line) => (line.product.id === productId ? { ...line, ...changes } : line)))

  const removeLine = (productId) => setCart((current) => current.filter((line) => line.product.id !== productId))

  const subtotal = cart.reduce((sum, line) => sum + Number(line.quantity || 0) * Number(line.unit_price || 0), 0)
  const total = Math.max(subtotal - Number(discount || 0), 0)
  const itemCount = cart.reduce((sum, line) => sum + Number(line.quantity || 0), 0)
  const overStock = cart.some((line) => Number(line.quantity) > Number(line.product.stock_quantity))
  const invalid = cart.some((line) => !(Number(line.quantity) > 0) || line.unit_price === '')

  const clearCart = () => {
    setCart([])
    setDiscount('')
    setCustomer({ customer_name: '', customer_phone: '', note: '' })
    setShowDetails(false)
    setPaymentMethod('cash')
  }

  // No internet: keep the sale on this phone; it is sent automatically later (see OfflineContext)
  const saveOffline = (body) => {
    const sale = {
      offline: true,
      receipt_number: t('pos.pendingReceipt'),
      sold_at: body.sold_at,
      payment_method: body.payment_method,
      customer_name: body.customer_name,
      discount: body.discount,
      total_amount: total,
      items: cart.map((line) => ({
        id: line.product.id,
        product_name: line.product.name,
        quantity: line.quantity,
        unit_price: line.unit_price,
        subtotal: Number(line.quantity) * Number(line.unit_price),
      })),
    }
    const saved = offline.save({
      id: body.client_id,
      kind: 'sale',
      body: { ...body, recorded_offline: true },
      summary: { amount: total, label: sale.items.map((item) => item.product_name).join(', ') },
    })
    if (!saved) return false
    // Show the lower stock on this phone straight away
    products.setData((data) =>
      data && {
        ...data,
        results: data.results.map((p) => {
          const line = cart.find((l) => l.product.id === p.id)
          return line ? { ...p, stock_quantity: String(Number(p.stock_quantity) - Number(line.quantity)) } : p
        }),
      },
    )
    setReceipt(sale)
    clearCart()
    return true
  }

  const completeSale = async () => {
    setSaving(true)
    setError(null)
    const body = {
      // The same id is used if the sale has to be sent again later, so it is never saved twice
      client_id: newClientId(),
      sold_at: new Date().toISOString(),
      items: cart.map((line) => ({
        product: line.product.id,
        quantity: line.quantity,
        unit_price: line.unit_price,
      })),
      payment_method: paymentMethod,
      discount: discount || 0,
      ...customer,
    }
    try {
      const sale = await api.post('/sales/', body)
      setReceipt(sale)
      clearCart()
      products.reload()
      // The sale may have triggered a low-stock alert
      notifications.refresh()
    } catch (err) {
      if (err.status !== 0 || !saveOffline(body)) setError(err)
    } finally {
      setSaving(false)
    }
  }

  const query = search.trim().toLowerCase()
  const productList = (products.data?.results ?? []).filter(
    (p) => offline.online || !query || p.name.toLowerCase().includes(query) || (p.sku || '').toLowerCase().includes(query),
  )

  return (
    <>
      <PageHeader title={t('pos.title')} />

      <div className="grid gap-5 pb-20 lg:grid-cols-5 lg:pb-0">
        {/* Products to choose from */}
        <div className="lg:col-span-3">
          <div className="relative mb-3">
            <Icon name="search" size={18} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('pos.searchPlaceholder')}
              aria-label={t('pos.searchPlaceholder')}
              className="h-12 w-full rounded-xl border border-line-strong bg-card pr-3 pl-10 text-base text-ink placeholder:text-muted focus:outline-2 focus:outline-brand"
            />
          </div>
          <ErrorBox error={products.error} onRetry={products.reload} />
          {products.loading && !products.data ? (
            <Loading />
          ) : productList.length === 0 ? (
            <Card>
              <EmptyState icon="box" title={t('pos.noProducts')} />
            </Card>
          ) : (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {productList.map((p) => {
                const out = Number(p.stock_quantity) <= 0
                const inCart = cart.find((line) => line.product.id === p.id)
                return (
                  <button
                    key={p.id}
                    // Offline the stock shown may be old (another phone may have added stock), so allow it
                    disabled={out && offline.online}
                    onClick={() => addToCart(p)}
                    className={`relative rounded-xl border p-3 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                      inCart ? 'border-brand bg-brand-soft' : 'border-line bg-card hover:border-brand'
                    }`}
                  >
                    {inCart && (
                      <span className="absolute top-2 right-2 rounded-full bg-brand px-2 py-0.5 text-xs font-semibold text-white">
                        {formatQuantity(inCart.quantity)}
                      </span>
                    )}
                    <p className="line-clamp-2 pr-8 text-sm font-medium text-ink">{p.name}</p>
                    <p className="tabular mt-1 text-sm font-semibold text-ink">{formatMoney(p.selling_price)}</p>
                    <p className="mt-1 text-xs">
                      {out ? (
                        <Badge tone="bad">{t('pos.outOfStock')}</Badge>
                      ) : (
                        <span className={p.is_low_stock ? 'text-warn-ink' : 'text-muted'}>
                          {t('pos.inStock', { qty: formatQuantity(p.stock_quantity) })}
                        </span>
                      )}
                    </p>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {/* The cart */}
        <div ref={cartRef} className="lg:col-span-2">
          <Card title={t('pos.cart')} className="lg:sticky lg:top-6">
            {cart.length === 0 ? (
              <EmptyState icon="cart" title={t('pos.emptyCart')} />
            ) : (
              <div className="space-y-4">
                <ul className="divide-y divide-line">
                  {cart.map((line) => {
                    const tooMany = Number(line.quantity) > Number(line.product.stock_quantity)
                    return (
                      <li key={line.product.id} className="py-3 first:pt-0">
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-sm font-medium text-ink">{line.product.name}</p>
                          <button
                            onClick={() => removeLine(line.product.id)}
                            className="rounded p-1 text-muted hover:bg-bad-soft hover:text-bad"
                            aria-label={`${t('pos.remove')} ${line.product.name}`}
                          >
                            <Icon name="x" size={16} />
                          </button>
                        </div>
                        <div className="mt-2 flex items-center gap-2">
                          <div className="flex items-center rounded-lg border border-line-strong">
                            <button
                              onClick={() => updateLine(line.product.id, { quantity: String(Math.max(Number(line.quantity) - 1, 1)) })}
                              className="p-2 text-ink-2 hover:text-ink"
                              aria-label="-1"
                            >
                              <Icon name="minus" size={16} />
                            </button>
                            <input
                              type="number"
                              min="0"
                              step="any"
                              inputMode="decimal"
                              value={line.quantity}
                              onChange={(e) => updateLine(line.product.id, { quantity: e.target.value })}
                              aria-label={t('product.quantity')}
                              className="tabular w-14 bg-transparent text-center text-sm text-ink focus:outline-none"
                            />
                            <button
                              onClick={() => updateLine(line.product.id, { quantity: String(Number(line.quantity) + 1) })}
                              className="p-2 text-ink-2 hover:text-ink"
                              aria-label="+1"
                            >
                              <Icon name="plus" size={16} />
                            </button>
                          </div>
                          <span className="text-muted">×</span>
                          <input
                            type="number"
                            min="0"
                            step="any"
                            inputMode="decimal"
                            value={line.unit_price}
                            onChange={(e) => updateLine(line.product.id, { unit_price: e.target.value })}
                            aria-label={t('pos.price')}
                            className="tabular h-9 w-24 min-w-0 rounded-lg border border-line-strong bg-card px-2 text-sm text-ink focus:outline-2 focus:outline-brand"
                          />
                          <span className="tabular ml-auto text-sm font-semibold text-ink">
                            {formatMoney(Number(line.quantity || 0) * Number(line.unit_price || 0))}
                          </span>
                        </div>
                        {tooMany && (
                          <p className="mt-1 text-xs text-bad">
                            {t('pos.notEnough', { qty: formatQuantity(line.product.stock_quantity) })}
                          </p>
                        )}
                      </li>
                    )
                  })}
                </ul>

                <div className="grid grid-cols-2 gap-3 border-t border-line pt-4">
                  <Select
                    label={t('pos.paymentMethod')}
                    value={paymentMethod}
                    onChange={(e) => setPaymentMethod(e.target.value)}
                    options={PAYMENT_METHODS.map((m) => ({ value: m, label: t(`payment.${m}`) }))}
                  />
                  <Input
                    label={t('pos.discount')}
                    type="number"
                    min="0"
                    step="any"
                    inputMode="decimal"
                    value={discount}
                    onChange={(e) => setDiscount(e.target.value)}
                    placeholder="0"
                  />
                </div>

                <button
                  onClick={() => setShowDetails(!showDetails)}
                  className="text-sm font-medium text-brand-ink underline"
                  aria-expanded={showDetails}
                >
                  {t('pos.moreDetails')}
                </button>
                {showDetails && (
                  <div className="space-y-3">
                    <Input
                      label={t('pos.customerName')}
                      value={customer.customer_name}
                      onChange={(e) => setCustomer({ ...customer, customer_name: e.target.value })}
                    />
                    <PhoneInput
                      label={t('pos.customerPhone')}
                      value={customer.customer_phone}
                      onChange={(e) => setCustomer({ ...customer, customer_phone: e.target.value })}
                    />
                    <Input
                      label={t('pos.note')}
                      value={customer.note}
                      onChange={(e) => setCustomer({ ...customer, note: e.target.value })}
                    />
                  </div>
                )}

                <div className="space-y-1 border-t border-line pt-4 text-sm">
                  {Number(discount) > 0 && (
                    <>
                      <p className="flex justify-between text-ink-2">
                        <span>{t('pos.subtotal')}</span>
                        <span className="tabular">{formatMoney(subtotal)}</span>
                      </p>
                      <p className="flex justify-between text-ink-2">
                        <span>{t('pos.discount')}</span>
                        <span className="tabular">-{formatMoney(discount)}</span>
                      </p>
                    </>
                  )}
                  <p className="flex justify-between text-lg font-bold text-ink">
                    <span>{t('common.total')}</span>
                    <span className="tabular">{formatMoney(total)}</span>
                  </p>
                </div>

                <ErrorBox error={error} />
                <Button
                  size="lg"
                  icon="check"
                  className="w-full"
                  loading={saving}
                  disabled={(overStock && offline.online) || invalid || Number(discount) > subtotal}
                  onClick={completeSale}
                >
                  {t('pos.complete')}
                </Button>
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* Phone: a bar at the bottom that shows the total and jumps to the cart */}
      {cart.length > 0 && (
        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-card px-4 py-3 lg:hidden">
          <button
            onClick={() => cartRef.current?.scrollIntoView({ behavior: 'smooth' })}
            className="flex h-12 w-full items-center justify-between rounded-xl bg-brand px-4 font-semibold text-white"
          >
            <span>{t('pos.items', { count: formatQuantity(itemCount) })}</span>
            <span className="flex items-center gap-2">
              {formatMoney(total)} <Icon name="arrowRight" size={18} />
            </span>
          </button>
        </div>
      )}

      {receipt && <Receipt sale={receipt} onClose={() => setReceipt(null)} />}
    </>
  )
}
