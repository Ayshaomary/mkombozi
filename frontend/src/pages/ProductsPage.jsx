import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import Icon from '../components/Icon'
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
  Select,
} from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { api } from '../lib/api'
import { formatDateTime, formatMoney, formatQuantity } from '../lib/format'
import { useApi, usePaginated } from '../lib/useApi'
import { useDebounce } from '../lib/useDebounce'
import { SHOP_TYPES, UNITS } from '../lib/constants'

const EMPTY_PRODUCT = {
  name: '',
  category: '',
  unit: 'piece',
  cost_price: '',
  selling_price: '',
  opening_stock: '',
  low_stock_threshold: '5',
  sku: '',
  is_material: false,
  is_active: true,
}

// Category names that fit a type of shop and aren't added yet, e.g. a food shop: Food, Drinks, Other.
// Without `browseType`, the user's own type of shop is used.
function useCategorySuggestions(categories, browseType) {
  const { t } = useLanguage()
  const { user } = useAuth()
  const ownType = user?.business?.business_type || 'other'
  const type = browseType || ownType
  const list = (key) => {
    const value = t(key)
    return Array.isArray(value) ? value : []
  }
  const taken = new Set(categories.map((c) => c.name.trim().toLowerCase()))
  return {
    type,
    ownType,
    names: [...list(`categorySuggestions.${type}`), ...list('categorySuggestions.all')].filter(
      (name) => !taken.has(name.toLowerCase()),
    ),
  }
}

// In the category list, a suggestion that doesn't exist yet; it is created when the product is saved
const NEW_CATEGORY = 'new:'

function ProductFormModal({ product, categories, onClose, onSaved, onCategoriesChanged }) {
  const { t } = useLanguage()
  const suggestions = useCategorySuggestions(categories)
  const isNew = !product.id
  const [form, setForm] = useState(() =>
    isNew ? EMPTY_PRODUCT : { ...EMPTY_PRODUCT, ...product, category: product.category ?? '' },
  )
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
    let category = form.category || null
    const body = {
      name: form.name,
      unit: form.unit,
      cost_price: form.cost_price,
      // Raw materials are not sold, so they need no selling price
      selling_price: form.is_material && form.selling_price === '' ? 0 : form.selling_price,
      low_stock_threshold: form.low_stock_threshold || 0,
      sku: form.sku,
      is_material: form.is_material,
      is_active: form.is_active,
    }
    if (isNew && form.opening_stock) body.opening_stock = form.opening_stock
    try {
      if (String(category).startsWith(NEW_CATEGORY)) {
        category = (await api.post('/categories/', { name: category.slice(NEW_CATEGORY.length) })).id
        // If saving the product fails, trying again uses this category instead of adding it twice
        setForm((current) => ({ ...current, category }))
        onCategoriesChanged()
      }
      body.category = category
      if (isNew) await api.post('/products/', body)
      else await api.patch(`/products/${product.id}/`, body)
      onSaved()
    } catch (err) {
      setError(err)
      setSaving(false)
    }
  }

  const belowCost = !form.is_material && form.cost_price && form.selling_price && Number(form.selling_price) < Number(form.cost_price)

  return (
    <Modal
      open
      onClose={onClose}
      title={isNew ? t('product.add') : t('product.editTitle')}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form="product-form" loading={saving}>
            {t('common.save')}
          </Button>
        </>
      }
    >
      <form id="product-form" onSubmit={save} className="space-y-4">
        {error && Object.keys(error.fields).length === 0 && <ErrorBox error={error} />}
        <Input label={t('product.name')} required autoFocus {...field('name')} />
        <div className="grid grid-cols-2 gap-3">
          <Select
            label={t('product.category')}
            options={[
              { value: '', label: t('product.noCategory') },
              ...categories.map((c) => ({ value: c.id, label: c.name })),
              ...suggestions.names.map((name) => ({ value: NEW_CATEGORY + name, label: `+ ${name}` })),
            ]}
            {...field('category')}
          />
          <Select
            label={t('product.unit')}
            options={UNITS.map((u) => ({ value: u, label: t(`units.${u}`) }))}
            {...field('unit')}
          />
        </div>
        <div>
          <Checkbox
            label={t('product.isMaterial')}
            checked={form.is_material}
            onChange={(e) => setForm({ ...form, is_material: e.target.checked })}
          />
          <p className="mt-1 text-xs text-muted">{t('product.isMaterialHint')}</p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Input label={t('product.costPrice')} type="number" min="0" step="any" inputMode="decimal" required {...field('cost_price')} />
          {!form.is_material && (
            <Input
              label={t('product.sellingPrice')}
              type="number"
              min="0"
              step="any"
              inputMode="decimal"
              required
              {...field('selling_price')}
            />
          )}
        </div>
        {belowCost && (
          <p className="flex items-center gap-2 text-sm text-warn-ink">
            <Icon name="alert" size={16} /> {t('product.sellingBelowCost')}
          </p>
        )}
        <div className="grid grid-cols-2 gap-3">
          {isNew && (
            <Input label={t('product.openingStock')} type="number" min="0" step="any" inputMode="decimal" {...field('opening_stock')} />
          )}
          <Input
            label={t('product.lowStockThreshold')}
            type="number"
            min="0"
            step="any"
            inputMode="decimal"
            {...field('low_stock_threshold')}
          />
        </div>
        <Input label={`${t('product.sku')} (${t('common.optional')})`} {...field('sku')} />
        {!isNew && (
          <Checkbox
            label={t('product.active')}
            checked={form.is_active}
            onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
          />
        )}
      </form>
    </Modal>
  )
}

function StockModal({ product, onClose, onSaved }) {
  const { t } = useLanguage()
  const [form, setForm] = useState({ movement_type: 'purchase', quantity: '', new_cost_price: '', note: '' })
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
    const body = { movement_type: form.movement_type, quantity: form.quantity, note: form.note }
    if (form.movement_type === 'purchase' && form.new_cost_price) body.new_cost_price = form.new_cost_price
    try {
      await api.post(`/products/${product.id}/stock/`, body)
      onSaved()
    } catch (err) {
      setError(err)
      setSaving(false)
    }
  }

  const isAdjustment = form.movement_type === 'adjustment'

  return (
    <Modal
      open
      onClose={onClose}
      title={t('product.stockTitle', { name: product.name })}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form="stock-form" loading={saving}>
            {t('common.save')}
          </Button>
        </>
      }
    >
      <form id="stock-form" onSubmit={save} className="space-y-4">
        <p className="text-sm text-ink-2">
          {t('product.stock')}: <strong className="text-ink">{formatQuantity(product.stock_quantity)}</strong>
        </p>
        {error && Object.keys(error.fields).length === 0 && <ErrorBox error={error} />}
        <Select
          label={t('product.movementType')}
          options={['purchase', 'return', 'adjustment'].map((m) => ({ value: m, label: t(`movement.${m}`) }))}
          {...field('movement_type')}
        />
        <Input
          label={t('product.quantity')}
          type="number"
          step="any"
          inputMode="decimal"
          min={isAdjustment ? undefined : '0'}
          hint={isAdjustment ? t('product.quantityHintAdjustment') : undefined}
          required
          autoFocus
          {...field('quantity')}
        />
        {form.movement_type === 'purchase' && (
          <Input
            label={`${t('product.newCostPrice')} (${t('common.optional')})`}
            type="number"
            min="0"
            step="any"
            inputMode="decimal"
            placeholder={String(Number(product.cost_price))}
            {...field('new_cost_price')}
          />
        )}
        <Input label={`${t('product.note')} (${t('common.optional')})`} {...field('note')} />
      </form>
    </Modal>
  )
}

function HistoryModal({ product, onClose }) {
  const { t, lang } = useLanguage()
  const { data, loading, error } = useApi('/stock-movements/', { product: product.id })
  return (
    <Modal open onClose={onClose} title={t('product.historyTitle', { name: product.name })} wide>
      {loading && <Loading />}
      <ErrorBox error={error} />
      {data && (
        <ul className="divide-y divide-line">
          {data.results.map((m) => (
            <li key={m.id} className="flex items-start justify-between gap-3 py-3 text-sm">
              <div className="min-w-0">
                <p className="font-medium text-ink">{t(`movement.${m.movement_type}`)}</p>
                <p className="text-xs text-muted">
                  {formatDateTime(m.created_at, lang)}
                  {m.created_by_name && ` · ${m.created_by_name}`}
                  {m.note && ` · ${m.note}`}
                </p>
              </div>
              <div className="shrink-0 text-right">
                <p className={`tabular font-semibold ${Number(m.quantity) < 0 ? 'text-bad' : 'text-good'}`}>
                  {Number(m.quantity) > 0 ? '+' : ''}
                  {formatQuantity(m.quantity)}
                </p>
                <p className="text-xs text-muted">
                  {t('product.stockAfter')}: {formatQuantity(m.stock_after)}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Modal>
  )
}

function CategoriesModal({ categories, onClose, onChanged }) {
  const { t } = useLanguage()
  const [browseType, setBrowseType] = useState(null)
  const suggestions = useCategorySuggestions(categories, browseType)
  const [name, setName] = useState('')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const add = async (event, suggested) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await api.post('/categories/', { name: suggested ?? name })
      if (!suggested) setName('')
      onChanged()
    } catch (err) {
      setError(err)
    } finally {
      setSaving(false)
    }
  }

  const remove = async (category) => {
    if (!window.confirm(t('common.confirmDelete'))) return
    try {
      await api.delete(`/categories/${category.id}/`)
      onChanged()
    } catch (err) {
      setError(err)
    }
  }

  return (
    <Modal open onClose={onClose} title={t('product.categories')}>
      <div className="mb-4">
        <Select
          label={t('product.suggestionsFor')}
          hint={t('product.suggestedHint')}
          value={suggestions.type}
          onChange={(e) => setBrowseType(e.target.value)}
          options={SHOP_TYPES.map((type) => ({
            value: type,
            label: type === suggestions.ownType ? `${t(`shopTypes.${type}`)} ★` : t(`shopTypes.${type}`),
          }))}
        />
        {suggestions.names.length === 0 ? (
          <p className="mt-2 text-sm text-muted">{t('product.allSuggestionsAdded')}</p>
        ) : (
          <div className="mt-3 flex flex-wrap gap-2">
            {suggestions.names.map((suggested) => (
              <button
                key={suggested}
                type="button"
                disabled={saving}
                onClick={(event) => add(event, suggested)}
                className="inline-flex items-center gap-1 rounded-full border border-line-strong px-3 py-1.5 text-sm text-ink hover:border-brand hover:bg-brand-soft disabled:opacity-50"
              >
                <Icon name="plus" size={14} /> {suggested}
              </button>
            ))}
          </div>
        )}
      </div>
      <form onSubmit={add} className="mb-4 flex items-start gap-2">
        <Input
          className="flex-1"
          placeholder={t('product.newCategory')}
          aria-label={t('product.newCategory')}
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <Button type="submit" icon="plus" loading={saving}>
          {t('common.add')}
        </Button>
      </form>
      <ErrorBox error={error} />
      {categories.length === 0 ? (
        <EmptyState icon="tag" title={t('product.noCategories')} />
      ) : (
        <ul className="divide-y divide-line">
          {categories.map((c) => (
            <li key={c.id} className="flex items-center justify-between py-2 text-sm">
              <span className="text-ink">
                {c.name} <span className="text-muted">({c.product_count})</span>
              </span>
              <button
                onClick={() => remove(c)}
                className="rounded-lg p-1.5 text-muted hover:bg-bad-soft hover:text-bad"
                aria-label={`${t('common.delete')} ${c.name}`}
              >
                <Icon name="trash" size={16} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </Modal>
  )
}

function IconButton({ icon, label, onClick, danger }) {
  return (
    <button
      onClick={onClick}
      title={label}
      aria-label={label}
      className={`rounded-lg p-2 text-ink-2 ${danger ? 'hover:bg-bad-soft hover:text-bad' : 'hover:bg-soft hover:text-ink'}`}
    >
      <Icon name={icon} size={18} />
    </button>
  )
}

export default function ProductsPage() {
  const { t } = useLanguage()
  const { isOwner } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [lowStock, setLowStock] = useState(searchParams.get('low_stock') === '1')
  const [kind, setKind] = useState('')
  // Which modal is open: { type: 'form' | 'stock' | 'history' | 'categories', product }
  const [modal, setModal] = useState(() => (searchParams.get('add') === '1' && isOwner ? { type: 'form', product: {} } : null))
  const debouncedSearch = useDebounce(search)

  const categoriesApi = useApi('/categories/')
  const categories = categoriesApi.data ?? []
  const products = usePaginated('/products/', {
    search: debouncedSearch,
    category,
    kind,
    low_stock: lowStock ? 'true' : '',
  })

  const closeModal = () => {
    setModal(null)
    if (searchParams.has('add')) setSearchParams({}, { replace: true })
  }
  const afterSave = () => {
    closeModal()
    products.reload()
    categoriesApi.reload()
  }

  const remove = async (product) => {
    if (!window.confirm(t('product.deleteConfirm'))) return
    try {
      await api.delete(`/products/${product.id}/`)
      products.reload()
    } catch (err) {
      window.alert(err.message)
    }
  }

  const filtering = debouncedSearch || category || kind || lowStock

  return (
    <>
      <PageHeader
        title={t('product.title')}
        subtitle={isOwner ? undefined : t('product.viewOnly')}
        actions={
          isOwner && (
            <>
              <Button variant="secondary" icon="tag" onClick={() => setModal({ type: 'categories' })}>
                {t('product.manageCategories')}
              </Button>
              <Button icon="plus" onClick={() => setModal({ type: 'form', product: {} })}>
                {t('product.add')}
              </Button>
            </>
          )
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative min-w-0 flex-1 basis-60">
          <Icon name="search" size={18} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('product.searchPlaceholder')}
            aria-label={t('product.searchPlaceholder')}
            className="h-10 w-full rounded-lg border border-line-strong bg-card pr-3 pl-10 text-sm text-ink placeholder:text-muted focus:outline-2 focus:outline-brand"
          />
        </div>
        {categories.length > 0 && (
          <Select
            aria-label={t('product.category')}
            className="w-44"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            options={[{ value: '', label: t('common.all') }, ...categories.map((c) => ({ value: c.id, label: c.name }))]}
          />
        )}
        <Select
          aria-label={t('product.kind')}
          className="w-44"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          options={[
            { value: '', label: t('product.allKinds') },
            { value: 'goods', label: t('product.forSale') },
            { value: 'material', label: t('product.materials') },
          ]}
        />
        <Checkbox label={t('product.lowStockOnly')} checked={lowStock} onChange={(e) => setLowStock(e.target.checked)} />
      </div>

      <ErrorBox error={products.error} onRetry={products.reload} />

      <Card padded={false}>
        {products.loading && products.items.length === 0 ? (
          <Loading />
        ) : products.items.length === 0 ? (
          <EmptyState icon="box" title={filtering ? t('product.noMatch') : t('product.empty')}>
            {isOwner && !filtering && (
              <Button icon="plus" onClick={() => setModal({ type: 'form', product: {} })}>
                {t('product.add')}
              </Button>
            )}
          </EmptyState>
        ) : (
          <ul className="divide-y divide-line">
            {products.items.map((p) => (
              <li key={p.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
                <div className="min-w-0 flex-1 basis-48">
                  <p className="flex flex-wrap items-center gap-2 font-medium text-ink">
                    {p.name}
                    {p.is_material && <Badge tone="warn">{t('product.material')}</Badge>}
                    {!p.is_active && <Badge>{t('product.inactive')}</Badge>}
                  </p>
                  <p className="text-xs text-muted">
                    {[p.category_name, t(`units.${p.unit}`), p.sku].filter(Boolean).join(' · ')}
                  </p>
                </div>
                <div className="w-48 text-sm">
                  {/* Raw materials have no selling price; show what they cost instead */}
                  <p className="tabular font-semibold text-ink">
                    {formatMoney(p.is_material ? p.cost_price : p.selling_price)}
                  </p>
                  {isOwner && (
                    <p className="tabular text-xs text-muted">
                      {t('product.costPrice')}: {formatMoney(p.cost_price)}
                    </p>
                  )}
                </div>
                <div className="w-24 text-sm">
                  <p className="tabular font-semibold text-ink">{formatQuantity(p.stock_quantity)}</p>
                  {p.is_low_stock ? (
                    <Badge tone={Number(p.stock_quantity) <= 0 ? 'bad' : 'warn'}>
                      {/* Below zero: sales made offline sold more than the stock on record */}
                      {Number(p.stock_quantity) < 0
                        ? t('product.checkStock')
                        : Number(p.stock_quantity) <= 0
                          ? t('pos.outOfStock')
                          : t('product.low')}
                    </Badge>
                  ) : (
                    <p className="text-xs text-muted">{t('product.stock')}</p>
                  )}
                </div>
                <div className="flex items-center gap-0.5">
                  {isOwner && (
                    <IconButton icon="stack" label={t('product.updateStock')} onClick={() => setModal({ type: 'stock', product: p })} />
                  )}
                  <IconButton icon="history" label={t('product.history')} onClick={() => setModal({ type: 'history', product: p })} />
                  {isOwner && (
                    <>
                      <IconButton icon="edit" label={t('common.edit')} onClick={() => setModal({ type: 'form', product: p })} />
                      <IconButton icon="trash" label={t('common.delete')} danger onClick={() => remove(p)} />
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {products.hasMore && (
        <div className="mt-4 text-center">
          <Button variant="secondary" loading={products.loading} onClick={products.loadMore}>
            {t('common.loadMore')}
          </Button>
        </div>
      )}

      {modal?.type === 'form' && (
        <ProductFormModal
          product={modal.product}
          categories={categories}
          onClose={closeModal}
          onSaved={afterSave}
          onCategoriesChanged={categoriesApi.reload}
        />
      )}
      {modal?.type === 'stock' && <StockModal product={modal.product} onClose={closeModal} onSaved={afterSave} />}
      {modal?.type === 'history' && <HistoryModal product={modal.product} onClose={closeModal} />}
      {modal?.type === 'categories' && (
        <CategoriesModal categories={categories} onClose={closeModal} onChanged={categoriesApi.reload} />
      )}
    </>
  )
}
