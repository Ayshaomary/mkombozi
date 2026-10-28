import { useId, useState } from 'react'
import Icon from '../components/Icon'
import {
  Badge,
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
import { UNITS } from '../lib/constants'
import { formatDateTime, formatMoney, formatQuantity } from '../lib/format'
import { useApi, usePaginated } from '../lib/useApi'

const round2 = (value) => Math.round(value * 100) / 100

// Every active product, the materials used most lately first (see production/views.py, materials)
function useStockItems() {
  const products = useApi('/production/materials/')
  return { ...products, items: products.data ?? [] }
}

// A material line names a material. If the business has a product with that name it is used,
// otherwise the server makes a new raw material with the typed unit and price.
const sameName = (a, b) => a.trim().toLowerCase() === b.trim().toLowerCase()
const findProduct = (products, name) => (name.trim() ? products.find((p) => sameName(p.name, name)) : undefined)
const emptyLine = () => ({ name: '', quantity: '', unit: 'kg', unit_cost: '' })

function lineCost(line, products) {
  const product = findProduct(products, line.name)
  return Number(product ? product.cost_price : line.unit_cost || 0) * Number(line.quantity || 0)
}

// The lines as the API expects them
function toItems(lines, products) {
  return lines
    .filter((line) => line.name.trim() && Number(line.quantity) > 0)
    .map((line) => {
      const product = findProduct(products, line.name)
      if (product) return { material: product.id, quantity: line.quantity }
      return { name: line.name.trim(), new_unit: line.unit, new_unit_cost: line.unit_cost || 0, quantity: line.quantity }
    })
}

// The list of materials used, shared by production and recipes: [{ name, quantity, unit, unit_cost }]
function MaterialLines({ lines, onChange, products, excludeId, showStock, errors }) {
  const { t } = useLanguage()
  const listId = useId()
  const choices = products.filter((p) => String(p.id) !== String(excludeId))
  const update = (index, changes) => onChange(lines.map((line, i) => (i === index ? { ...line, ...changes } : line)))

  return (
    <div className="space-y-2">
      {/* Suggestions while typing, in the order of the list: most used first */}
      <datalist id={listId}>
        {choices.map((p) => (
          <option key={p.id} value={p.name} />
        ))}
      </datalist>
      {lines.map((line, index) => {
        const material = findProduct(choices, line.name)
        const isNew = line.name.trim() && !material
        const short = showStock && material && Number(line.quantity) > Number(material.stock_quantity)
        return (
          <div key={index} className="rounded-lg border border-line p-2">
            <div className="flex items-start gap-2">
              <Input
                className="min-w-0 flex-1"
                aria-label={t('production.material')}
                placeholder={t('production.typeMaterial')}
                list={listId}
                autoComplete="off"
                value={line.name}
                onChange={(e) => update(index, { name: e.target.value })}
              />
              <Input
                className="w-24"
                aria-label={t('production.amount')}
                placeholder={t('production.amount')}
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
                {line.quantity && ` · ${formatMoney(lineCost(line, choices))}`}
                {showStock &&
                  ` · ${t(short ? 'production.notEnough' : 'production.inStock', { qty: formatQuantity(material.stock_quantity) })}`}
              </p>
            )}
            {isNew && (
              <div className="mt-2 rounded-md bg-soft p-2">
                <p className="mb-2 flex flex-wrap items-center gap-2 text-xs text-ink-2">
                  <Badge tone="good">{t('production.new')}</Badge>
                  {showStock ? t('production.newMaterialBought') : t('production.newMaterial')}
                </p>
                <div className="grid grid-cols-2 gap-2">
                  <Select
                    aria-label={t('product.unit')}
                    value={line.unit}
                    onChange={(e) => update(index, { unit: e.target.value })}
                    options={UNITS.map((u) => ({ value: u, label: t(`units.${u}`) }))}
                  />
                  <Input
                    aria-label={t('production.pricePerUnit')}
                    placeholder={t('production.pricePerUnit')}
                    type="number"
                    min="0"
                    step="any"
                    inputMode="decimal"
                    required
                    value={line.unit_cost}
                    onChange={(e) => update(index, { unit_cost: e.target.value })}
                  />
                </div>
              </div>
            )}
          </div>
        )
      })}
      {errors && <p className="text-sm text-bad">{errors}</p>}
      <Button type="button" size="sm" variant="secondary" icon="plus" onClick={() => onChange([...lines, emptyLine()])}>
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
      ...emptyLine(),
      name: item.material_name,
      quantity: String(round2((Number(item.quantity) * Number(quantity || 0)) / Number(rec.output_quantity))),
    }))

  const chooseProduct = (productId) => {
    const rec = recipeFor(productId)
    const quantity = rec ? String(Number(rec.output_quantity)) : form.quantity
    setForm({ ...form, product: productId, quantity })
    setLines(rec ? fromRecipe(rec, quantity) : [emptyLine()])
    setLinesEdited(false)
  }

  const changeQuantity = (quantity) => {
    setForm({ ...form, quantity })
    if (recipe && !linesEdited) setLines(fromRecipe(recipe, quantity))
  }

  const byId = Object.fromEntries(stock.items.map((p) => [String(p.id), p]))
  const product = byId[form.product]
  const materials = stock.items.filter((p) => String(p.id) !== form.product)
  const materialsCost = lines.reduce((sum, line) => sum + lineCost(line, materials), 0)
  const totalCost = materialsCost + Number(form.extra_cost || 0)
  const perUnit = Number(form.quantity) > 0 ? totalCost / Number(form.quantity) : 0
  const ready = form.product && Number(form.quantity) > 0 && toItems(lines, materials).length > 0

  // The materials this business uses most, one tap to add
  const frequent = materials
    .filter((p) => p.times_used > 0 && !lines.some((line) => sameName(line.name, p.name)))
    .slice(0, 6)
  const addFrequent = (product) => {
    setLinesEdited(true)
    const line = { ...emptyLine(), name: product.name }
    const blank = lines.findIndex((l) => !l.name.trim())
    setLines(blank >= 0 ? lines.map((l, i) => (i === blank ? line : l)) : [...lines, line])
  }

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
        items: toItems(lines, materials),
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
              {frequent.length > 0 && (
                <div className="mb-2">
                  <p className="mb-1 text-xs text-muted">{t('production.frequent')}</p>
                  <div className="flex flex-wrap gap-2">
                    {frequent.map((p) => (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => addFrequent(p)}
                        className="inline-flex items-center gap-1 rounded-full border border-line-strong px-3 py-1 text-sm text-ink hover:border-brand hover:bg-brand-soft"
                      >
                        <Icon name="plus" size={14} /> {p.name}
                      </button>
                    ))}
                  </div>
                </div>
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
      ? recipe.items.map((i) => ({ ...emptyLine(), name: i.material_name, quantity: String(Number(i.quantity)) }))
      : [emptyLine()],
  )
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const save = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    const materials = stock.items.filter((p) => String(p.id) !== form.product)
    const body = { ...form, items: toItems(lines, materials) }
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
