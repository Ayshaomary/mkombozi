// Choices that match the Django models (sales.PaymentMethod and expenses.Expense.Category)
export const PAYMENT_METHODS = ['cash', 'mpesa', 'tigopesa', 'airtelmoney', 'halopesa', 'bank', 'credit']

export const EXPENSE_CATEGORIES = [
  'rent',
  'salaries',
  'transport',
  'utilities',
  'communication',
  'taxes',
  'repairs',
  'marketing',
  'other',
]

// Types of shop (same as Business.Type in accounts/models.py). Each has its own suggested categories.
export const SHOP_TYPES = [
  'supermarket',
  'food',
  'cosmetics',
  'clothing',
  'accessories',
  'hardware',
  'electronics',
  'pharmacy',
  'stationery',
  'agrovet',
  'other',
]

// What the owner can allow each staff member (same as Permission in accounts/models.py)
export const PERMISSIONS = ['sales', 'expenses', 'products', 'production', 'reports', 'manage']

// Quick choices for the owner; they can also tick boxes one by one
export const PERMISSION_PRESETS = {
  salesOnly: ['sales', 'expenses'],
  products: ['sales', 'expenses', 'products'],
  productsProduction: ['sales', 'expenses', 'products', 'production'],
  everything: PERMISSIONS,
}

// Same as Product.Unit in inventory/models.py
export const UNITS = ['piece', 'kg', 'litre', 'metre', 'box', 'packet', 'dozen', 'bag']

// 'controlnumber' is only offered when the server has ClickPesa switched on
export const SUBSCRIPTION_PROVIDERS = ['mpesa', 'tigopesa', 'airtelmoney', 'halopesa', 'controlnumber', 'manual']

// How to pay a ClickPesa control number on each network. M-Pesa's business number comes from the server.
export const CONTROL_NUMBER_NETWORKS = [
  { provider: 'mpesa', dial: '*150*00#', menu: 'Lipa kwa M-Pesa' },
  { provider: 'tigopesa', dial: '*150*01#', menu: 'Lipia Bili', business: '889999' },
  { provider: 'airtelmoney', dial: '*150*60#', menu: 'Lipia Bili', business: '901030' },
  { provider: 'halopesa', dial: '*150*88#', menu: 'Lipia Bili', business: '889999' },
]

// How each mobile-money network's numbers start (same list as NETWORK_PREFIXES in subscriptions/models.py)
export const NETWORK_PREFIXES = {
  mpesa: ['074', '075', '076', '079'],
  tigopesa: ['065', '067', '071', '077'],
  airtelmoney: ['068', '069', '078'],
  halopesa: ['061', '062'],
}

// "+255 742 345 678" or "0742345678" -> "074". Null until the number is complete.
export function phonePrefix(phone) {
  const digits = String(phone || '').replace(/\D/g, '')
  if (digits.length === 12 && digits.startsWith('255')) return '0' + digits.slice(3, 5)
  if (digits.length === 10 && digits.startsWith('0')) return digits.slice(0, 3)
  return null
}
