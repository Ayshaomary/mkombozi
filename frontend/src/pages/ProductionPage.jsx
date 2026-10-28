import { useState } from 'react'
import Icon from '../components/Icon'
import {
  Button,
  Card,
  EmptyState,
  ErrorBox,
  Input,
  Loading,
  Modal,
  PageHeader,
  PeriodFilter,
  Select,
} from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { api } from '../lib/api'
import { formatDateTime, formatMoney, formatQuantity } from '../lib/format'
import { useApi, usePaginated } from '../lib/useApi'

const round2 = (value) => Math.round(value * 100) / 100

// All active products: raw materials first, since they are what production usually uses
function useStockItems() {
  const products = useApi('/products/', { active: 'true', page_size: 500 })
  const items = [...(products.data?.results ?? [])].sort(
    (a, b) => Number(b.is_material) - Number(a.is_material) || a.name.localeCompare(b.name),
  )
  return { ...products, items }
}

// The list of materials used: [{ material: id, quantity }], shared by production and recipes
function MaterialLines({ lines, onChange, products, excludeId, showStock, errors }) {
  const { t } = useLanguage()
  const byId = Object.fromEntries(products.map((p) => [String(p.id), p]))
  const update = (index, changes) => onChange(lines.map((line, i) => (i === index ? { ...line, ...changes } : line)))
  const options = [
    { value: '', label: t('production.chooseMaterial') },
    ...products
      .filter((p) => String(p.id) !== String(excludeId))
      .map((p) => ({
        value: String(p.id),
        label: `${p.name}${p.is_material ? '' : ` (${t('production.notMaterial')})`}`,
      })),
  ]

  return (
    <div className="space-y-2">
      {lines.map((line, index) => {
        const material = byId[String(line.material)]
        const short = showStock && material && Number(line.quantity) > Number(material.stock_quantity)
        return (
          <div key={index} className="rounded-lg border border-line p-2">
            <div className="flex items-start gap-2">
              <Select
                className="min-w-0 flex-1"
                aria-label={t('production.material')}
                value={String(line.material)}
                onChange={(e) => update(index, { material: e.target.value })}
                options={options}
              />
              <Input
                className="w-24"
                aria-label={t('production.amount')}
                type="number"
                min="0"
                step="any"
                inputMode="decimal"
                value={line.quantity}
                onChange={(e) => update(index, { quantity: e.target.value })}
              />
              <button
                type="button"
                onClick={() => onChange(lines.filter((_, i) => i !== index))}
                className="mt-1.5 rounded-lg p-1.5 text-muted hover:bg-bad-soft hover:text-bad"
                aria-label={t('common.delete')}
              >
                <Icon name="trash" size={16} />
              </button>
            </div>
            {material && (
              <p className={`mt-1 text-xs ${short ? 'text-bad' : 'text-muted'}`}>
                {t(`units.${material.unit}`)} · {formatMoney(material.cost_price)} {t('production.each')}
                {line.quantity && ` · ${formatMoney(Number(material.cost_price) * Number(line.quantity))}`}
                {showStock &&
                  ` · ${t(short ? 'production.notEnough' : 'production.inStock', { qty: formatQuantity(material.stock_quantity) })}`}
              </p>
            )}
          </div>
        )
      })}
      {errors && <p className="text-sm text-bad">{errors}</p>}
      <Button
        type="button"
        size="sm"
        variant="secondary"
        icon="plus"
        onClick={() => onChange([...lines, { material: '', quantity: '' }])}
      >
        {t('production.addMaterial')}
      </Button>
    </div>
  )
}

function RecordModal({ recipes, onClose, onSaved }) {
  const { t } = useLanguage()
  const stock = useStockItems()
  const [form, setForm] = useState({ product: '', quantity: '', extra_cost: '', note: '' })
  const [lines, setLines] = useState([])
  // Once the user changes the materials by hand, changing the quantity no longer resets them
  const [linesEdited, setLinesEdited] = useState(false)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const recipeFor = (productId) => recipes.find((r) => String(r.product) === String(productId))
  const recipe = recipeFor(form.product)
  const fromRecipe = (rec, quantity) =>
    rec.items.map((item) => ({
      material: String(item.material),
      quantity: String(round2((Number(item.quantity) * Number(quantity || 0)) / Number(rec.output_quantity))),
    }))

  const chooseProduct = (productId) => {
    const rec = recipeFor(productId)
    const quantity = rec ? String(Number(rec.output_quantity)) : form.quantity
    setForm({ ...form, product: productId, quantity })
    setLines(rec ? fromRecipe(rec, quantity) : [{ material: '', quantity: '' }])
    setLinesEdited(false)
  }

  const changeQuantity = (quantity) => {
    setForm({ ...form, quantity })
    if (recipe && !linesEdited) setLines(fromRecipe(recipe, quantity))
  }

  const byId = Object.fromEntries(stock.items.map((p) => [String(p.id), p]))
  const product = byId[form.product]
  const materialsCost = lines.reduce(
    (sum, line) => sum + Number(byId[String(line.material)]?.cost_price || 0) * Number(line.quantity || 0),
    0,
  )
  const totalCost = materialsCost + Number(form.extra_cost || 0)
  const perUnit = Number(form.quantity) > 0 ? totalCost / Number(form.quantity) : 0
  const ready = form.product && Number(form.quantity) > 0 && lines.some((l) => l.material && Number(l.quantity) > 0)

  const save = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await api.post('/production/', {
        product: form.product,
        quantity: form.quantity,
        extra_cost: form.extra_cost || 0,
        note: form.note,
        items: lines
          .filter((l) => l.material && Number(l.quantity) > 0)
          .map((l) => ({ material: l.material, quantity: l.quantity })),
      })
      onSaved()
    } catch (err) {
      setError(err)
      setSaving(false)
    }
  }

  const finished = stock.items.filter((p) => !p.is_material)
  return (
    <Modal
      open
      wide
      onClose={onClose}
      title={t('production.record')}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form="production-form" loading={saving} disabled={!ready}>
            {t('common.save')}
          </Button>
        </>
      }
    >
      <form id="production-form" onSubmit={save} className="space-y-4">
        {error && !error.fields?.items && <ErrorBox error={error} />}
        {stock.loading && !stock.data && <Loading />}
        <div className="grid gap-3 sm:grid-cols-3">
          <Select
            className="sm:col-span-2"
            label={t('production.product')}
            required
            value={form.product}
            onChange={(e) => chooseProduct(e.target.value)}
            options={[
              { value: '', label: t('production.chooseProduct') },
              ...finished.map((p) => ({ value: String(p.id), label: p.name })),
            ]}
          />
          <Input
            label={t('production.quantity')}
            type="number"
            min="0"
            step="any"
            inputMode="decimal"
            required
            hint={product && t(`units.${product.unit}`)}
            value={form.quantity}
            onChange={(e) => changeQuantity(e.target.value)}
            error={error?.fields?.quantity}
          />
        </div>

        {form.product && (
          <>
            <div>
              <p className="mb-1 text-sm font-medium text-ink-2">{t('production.materialsUsed')}</p>
              {recipe && (
                <p className="mb-2 text-xs text-muted">
                  {t('production.fromRecipe', { qty: formatQuantity(recipe.output_quantity) })}
                </p>
              )}
              <MaterialLines
                lines={lines}
                onChange={(next) => {
                  setLines(next)
                  setLinesEdited(true)
                }}
                products={stock.items}
                excludeId={form.product}
                showStock
                errors={error?.fields?.items}
              />
            </div>
            <Input
              label={`${t('production.extraCost')} (${t('common.optional')})`}
              hint={t('production.extraCostHint')}
              type="number"
              min="0"
              step="any"
              inputMode="decimal"
              value={form.extra_cost}
              onChange={(e) => setForm({ ...form, extra_cost: e.target.value })}
            />
            <Input
              label={`${t('production.note')} (${t('common.optional')})`}
              value={form.note}
              onChange={(e) => setForm({ ...form, note: e.target.value })}
            />
            <div className="space-y-1 rounded-lg bg-soft p-3 text-sm">
              <p className="flex justify-between text-ink-2">
                <span>{t('production.materialsCost')}</span>
                <span className="tabular">{formatMoney(materialsCost)}</span>
              </p>
              <p className="flex justify-between font-semibold text-ink">
                <span>{t('production.totalCost')}</span>
                <span className="tabular">{formatMoney(totalCost)}</span>
              </p>
              <p className="flex justify-between text-ink">
                <span>{t('production.costPerUnit')}</span>
                <span className="tabular font-semibold">{formatMoney(perUnit)}</span>
              </p>
              {product && Number(product.selling_price) > 0 && perUnit > 0 && (
                <p
                  className={`flex justify-between ${Number(product.selling_price) >= perUnit ? 'text-good' : 'text-bad'}`}
                >
                  <span>{t('production.profitPerUnit', { price: formatMoney(product.selling_price) })}</span>
                  <span className="tabular font-semibold">{formatMoney(Number(product.selling_price) - perUnit)}</span>
                </p>
              )}
            </div>
          </>
        )}
      </form>
    </Modal>
  )
}

function RecipeFormModal({ recipe, recipes, onClose, onSaved }) {
  const { t } = useLanguage()
  const stock = useStockItems()
  const isNew = !recipe.id
  const [form, setForm] = useState({
    product: recipe.product ? String(recipe.product) : '',
    output_quantity: recipe.output_quantity ? String(Number(recipe.output_quantity)) : '1',
    note: recipe.note ?? '',
  })
  const [lines, setLines] = useState(() =>
    recipe.items?.length
      ? recipe.items.map((i) => ({ material: String(i.material), quantity: String(Number(i.quantity)) }))
      : [{ material: '', quantity: '' }],
  )
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const save = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    const body = {
      ...form,
      items: lines
        .filter((l) => l.material && Number(l.quantity) > 0)
        .map((l) => ({ material: l.material, quantity: l.quantity })),
    }
    try {
      if (isNew) await api.post('/recipes/', body)
      else await api.patch(`/recipes/${recipe.id}/`, body)
      onSaved()
    } catch (err) {
      setError(err)
      setSaving(false)
    }
  }

  // A product can have only one recipe
  const taken = new Set(recipes.filter((r) => r.id !== recipe.id).map((r) => String(r.product)))
  const finished = stock.items.filter((p) => !p.is_material && !taken.has(String(p.id)))
  return (
    <Modal
      open
      wide
      onClose={onClose}
      title={isNew ? t('production.addRecipe') : t('production.editRecipe')}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form="recipe-form" loading={saving}>
            {t('common.save')}
          </Button>
        </>
      }
    >
      <form id="recipe-form" onSubmit={save} className="space-y-4">
        {error && !error.fields?.items && !error.fields?.product && <ErrorBox error={error} />}
        <div className="grid gap-3 sm:grid-cols-3">
          <Select
            className="sm:col-span-2"
            label={t('production.product')}
            required
            disabled={!isNew}
            value={form.product}
            onChange={(e) => setForm({ ...form, product: e.target.value })}
            error={error?.fields?.product}
            options={[
              { value: '', label: t('production.chooseProduct') },
              // When editing, the product can't change
              ...(isNew
                ? finished.map((p) => ({ value: String(p.id), label: p.name }))
                : [{ value: form.product, label: recipe.product_name }]),
            ]}
          />
          <Input
            label={t('production.batchMakes')}
            type="number"
            min="0"
            step="any"
            inputMode="decimal"
            required
            value={form.output_quantity}
            onChange={(e) => setForm({ ...form, output_quantity: e.target.value })}
            error={error?.fields?.output_quantity}
          />
        </div>
        <div>
          <p className="mb-2 text-sm font-medium text-ink-2">{t('production.recipeMaterials')}</p>
          <MaterialLines
            lines={lines}
            onChange={setLines}
            products={stock.items}
            excludeId={form.product}
            errors={error?.fields?.items}
          />
        </div>
        <Input
          label={`${t('production.note')} (${t('common.optional')})`}
          value={form.note}
          onChange={(e) => setForm({ ...form, note: e.target.value })}
        />
      </form>
    </Modal>
  )
}

function RecipesModal({ recipes, onClose, onChanged }) {
  const { t } = useLanguage()
  const { isOwner } = useAuth()
  const [editing, setEditing] = useState(null)
  const [error, setError] = useState(null)

  const remove = async (recipe) => {
    if (!window.confirm(t('common.confirmDelete'))) return
    try {
      await api.delete(`/recipes/${recipe.id}/`)
      onChanged()
    } catch (err) {
      setError(err)
    }
  }

  if (editing) {
    return (
      <RecipeFormModal
        recipe={editing}
        recipes={recipes}
        onClose={() => setEditing(null)}
        onSaved={() => {
          setEditing(null)
          onChanged()
        }}
      />
    )
  }

  return (
    <Modal
      open
      wide
      onClose={onClose}
      title={t('production.recipes')}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t('common.close')}
          </Button>
          {isOwner && (
            <Button icon="plus" onClick={() => setEditing({})}>
              {t('production.addRecipe')}
            </Button>
          )}
        </>
      }
    >
      <p className="mb-3 text-sm text-ink-2">{t('production.recipesHint')}</p>
      <ErrorBox error={error} />
      {recipes.length === 0 ? (
        <EmptyState icon="stack" title={t('production.noRecipes')} />
      ) : (
        <ul className="divide-y divide-line">
          {recipes.map((recipe) => (
            <li key={recipe.id} className="flex items-start justify-between gap-3 py-3 text-sm">
              <div className="min-w-0">
                <p className="font-medium text-ink">
                  {recipe.product_name}{' '}
                  <span className="font-normal text-muted">
                    · {t('production.batchOf', { qty: formatQuantity(recipe.output_quantity) })}
                  </span>
                </p>
                <p className="text-xs text-muted">
                  {recipe.items.map((i) => `${formatQuantity(i.quantity)} ${t(`units.${i.unit}`)} ${i.material_name}`).join(', ')}
                </p>
                <p className="mt-1 text-xs text-ink-2">
                  {t('production.recipeCost', { cost: formatMoney(recipe.cost_per_unit) })}
                  {Number(recipe.selling_price) > 0 && ` · ${t('production.sellsFor', { price: formatMoney(recipe.selling_price) })}`}
                </p>
              </div>
              {isOwner && (
                <div className="flex shrink-0 gap-1">
                  <button
                    onClick={() => setEditing(recipe)}
                    className="rounded-lg p-1.5 text-muted hover:bg-soft hover:text-ink"
                    aria-label={t('common.edit')}
                  >
                    <Icon name="edit" size={16} />
                  </button>
                  <button
                    onClick={() => remove(recipe)}
                    className="rounded-lg p-1.5 text-muted hover:bg-bad-soft hover:text-bad"
                    aria-label={t('common.delete')}
                  >
                    <Icon name="trash" size={16} />
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Modal>
  )
}

export default function ProductionPage() {
  const { t, lang } = useLanguage()
  const { isOwner } = useAuth()
  const [period, setPeriod] = useState('month')
  const [modal, setModal] = useState(null)
  const [error, setError] = useState(null)
  const runs = usePaginated('/production/', { period })
  const recipesApi = useApi('/recipes/')
  const recipes = recipesApi.data ?? []

  const cancel = async (run) => {
    if (!window.confirm(t('production.cancelConfirm'))) return
    setError(null)
    try {
      await api.delete(`/production/${run.id}/`)
      runs.reload()
    } catch (err) {
      setError(err)
    }
  }

  return (
    <>
      <PageHeader
        title={t('production.title')}
        actions={
          <>
            <Button variant="secondary" icon="stack" onClick={() => setModal('recipes')}>
              {t('production.recipes')}
            </Button>
            <Button icon="plus" onClick={() => setModal('record')}>
              {t('production.record')}
            </Button>
          </>
        }
      />
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <PeriodFilter value={period} onChange={setPeriod} includeAll />
        {runs.total !== null && (
          <p className="text-sm">
            <span className="text-muted">{t('production.periodCost')} </span>
            <span className="tabular font-semibold text-ink">{formatMoney(runs.total)}</span>
            <span className="text-muted"> · {t('production.batches', { count: runs.count })}</span>
          </p>
        )}
      </div>
      <ErrorBox error={error || runs.error} onRetry={error ? undefined : runs.reload} />

      <Card padded={false}>
        {runs.loading && runs.items.length === 0 ? (
          <Loading />
        ) : runs.items.length === 0 ? (
          <EmptyState icon="stack" title={t('production.empty')}>
            <p className="max-w-sm text-sm text-ink-2">{t('production.emptyHint')}</p>
          </EmptyState>
        ) : (
          <ul className="divide-y divide-line">
            {runs.items.map((run) => (
              <li key={run.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm">
                <div className="min-w-0">
                  <p className="font-medium text-ink">
                    {formatQuantity(run.quantity)} {run.unit ? t(`units.${run.unit}`) : ''} · {run.product_name}
                  </p>
                  <p className="text-xs text-muted">
                    {[run.batch_number, formatDateTime(run.produced_at, lang), run.created_by_name].filter(Boolean).join(' · ')}
                  </p>
                  <p className="truncate text-xs text-muted">
                    {run.items.map((i) => `${formatQuantity(i.quantity)} ${i.material_name}`).join(', ')}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <div className="text-right">
                    <p className="tabular font-semibold text-ink">{formatMoney(run.total_cost)}</p>
                    <p className="tabular text-xs text-muted">
                      {formatMoney(run.unit_cost)} {t('production.each')}
                    </p>
                  </div>
                  {isOwner && (
                    <button
                      onClick={() => cancel(run)}
                      className="rounded-lg p-2 text-muted hover:bg-bad-soft hover:text-bad"
                      aria-label={t('production.cancel')}
                      title={t('production.cancel')}
                    >
                      <Icon name="trash" size={18} />
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
      {runs.hasMore && (
        <div className="mt-4 text-center">
          <Button variant="secondary" loading={runs.loading} onClick={runs.loadMore}>
            {t('common.loadMore')}
          </Button>
        </div>
      )}

      {modal === 'record' && (
        <RecordModal
          recipes={recipes}
          onClose={() => setModal(null)}
          onSaved={() => {
            setModal(null)
            runs.reload()
          }}
        />
      )}
      {modal === 'recipes' && (
        <RecipesModal recipes={recipes} onClose={() => setModal(null)} onChanged={recipesApi.reload} />
      )}
    </>
  )
}
