// Who may do what (see Permission in accounts/models.py). The server checks it too.

import { PERMISSION_PRESETS } from './constants'

export function userCan(user, permission) {
  // Owners can do everything, also when their saved details are from before permissions existed
  return user?.role === 'owner' || Boolean(user?.permissions?.includes(permission))
}

// The first page a user may open after logging in
export function homePath(user) {
  if (!user?.business) return user?.is_staff ? '/manage' : '/login'
  if (userCan(user, 'reports')) return '/'
  if (userCan(user, 'sales')) return '/sell'
  return '/products'
}

const sameSet = (a, b) => a.length === b.length && a.every((item) => b.includes(item))

// Which quick choice (PERMISSION_PRESETS) a list of permissions matches, or 'custom'
export function presetOf(permissions) {
  return Object.keys(PERMISSION_PRESETS).find((key) => sameSet(PERMISSION_PRESETS[key], permissions)) ?? 'custom'
}
