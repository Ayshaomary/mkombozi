// All communication with the Django API goes through this file.

export const BASE_URL = import.meta.env.VITE_API_URL || '/api'
const TOKEN_KEY = 'mukombozi_tokens'

export function getTokens() {
  try {
    return JSON.parse(localStorage.getItem(TOKEN_KEY)) || null
  } catch {
    return null
  }
}

export function setTokens(tokens) {
  try {
    if (tokens) localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens))
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    // Storage can be blocked (private mode); the user just has to log in again next time
  }
}

export class ApiError extends Error {
  constructor(status, data) {
    super(extractMessage(data) || `Request failed (${status})`)
    this.status = status
    this.data = data
    // Field errors from Django, e.g. { phone: ['Already exists'] } -> { phone: 'Already exists' }
    this.fields = {}
    if (data && typeof data === 'object' && !Array.isArray(data)) {
      for (const [key, value] of Object.entries(data)) {
        if (key !== 'detail') this.fields[key] = Array.isArray(value) ? flatten(value) : String(value)
      }
    }
  }
}

function flatten(value) {
  return value.map((v) => (typeof v === 'object' ? Object.values(v).flat().join(' ') : v)).join(' ')
}

function extractMessage(data) {
  if (!data) return ''
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  if (Array.isArray(data)) return flatten(data)
  const first = Object.values(data)[0]
  return Array.isArray(first) ? flatten(first) : typeof first === 'string' ? first : ''
}

async function refreshAccessToken() {
  const tokens = getTokens()
  if (!tokens?.refresh) return false
  const response = await fetch(`${BASE_URL}/auth/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh: tokens.refresh }),
  })
  if (!response.ok) return false
  const data = await response.json()
  setTokens({ ...tokens, access: data.access })
  return true
}

// Tells the app whether the server could be reached (see OfflineContext). A phone can say it is
// online while it has no internet (e.g. Wi-Fi without data), so we go by real requests.
export const NETWORK_EVENT = 'mukombozi:network'
let serverReachable = true
export const lastServerReachable = () => serverReachable
function reportNetwork(online) {
  serverReachable = online
  window.dispatchEvent(new CustomEvent(NETWORK_EVENT, { detail: { online } }))
}

// Shared so that several requests failing at once trigger only one refresh
let refreshing = null

export async function request(path, { method = 'GET', body, params, retry = true } = {}) {
  let url = `${BASE_URL}${path}`
  if (params) {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''),
    )
    if (query.toString()) url += `?${query}`
  }

  const headers = { 'Content-Type': 'application/json' }
  const tokens = getTokens()
  if (tokens?.access) headers.Authorization = `Bearer ${tokens.access}`

  let response
  try {
    response = await fetch(url, { method, headers, body: body ? JSON.stringify(body) : undefined })
  } catch {
    reportNetwork(false)
    throw new ApiError(0, { detail: 'network' })
  }
  // The service worker answered with saved data because the server couldn't be reached
  reportNetwork(!response.headers.get('X-Mukombozi-Offline'))

  // Access token expired: get a new one with the refresh token and try once more
  if (response.status === 401 && retry && tokens?.refresh) {
    refreshing ??= refreshAccessToken().finally(() => (refreshing = null))
    if (await refreshing) return request(path, { method, body, params, retry: false })
    setTokens(null)
    window.dispatchEvent(new Event('mukombozi:logout'))
  }

  if (response.status === 204) return null
  const data = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(response.status, data)
  return data
}

export const api = {
  get: (path, params) => request(path, { params }),
  post: (path, body) => request(path, { method: 'POST', body }),
  put: (path, body) => request(path, { method: 'PUT', body }),
  patch: (path, body) => request(path, { method: 'PATCH', body }),
  delete: (path) => request(path, { method: 'DELETE' }),
}
