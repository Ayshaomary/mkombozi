// Sales and expenses recorded without internet wait here, on this phone, until they can be sent.
// Each user has their own outbox, and it survives logging out, so nothing recorded is lost.

const KEY_PREFIX = 'mukombozi_outbox_'
export const OUTBOX_CHANGED = 'mukombozi:outbox'

// Must match API_CACHE in public/sw.js
const API_CACHE = 'mukombozi-api'

// The id the server uses to save a record only once, even if the phone sends it twice
export function newClientId() {
  if (crypto.randomUUID) return crypto.randomUUID()
  // Older browsers, and pages opened over plain http on a local network
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = [...bytes].map((b) => b.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export function readOutbox(userId) {
  try {
    return JSON.parse(localStorage.getItem(KEY_PREFIX + userId)) || []
  } catch {
    return []
  }
}

// Returns false if the phone can't store it (storage full or blocked)
function writeOutbox(userId, items) {
  try {
    localStorage.setItem(KEY_PREFIX + userId, JSON.stringify(items))
  } catch {
    return false
  }
  window.dispatchEvent(new Event(OUTBOX_CHANGED))
  return true
}

// item: { id, kind: 'sale' | 'expense', body, summary: { amount, label }, created_at }
export function addToOutbox(userId, item) {
  return writeOutbox(userId, [...readOutbox(userId), { status: 'waiting', error: null, ...item }])
}

export function updateOutboxItem(userId, id, changes) {
  return writeOutbox(
    userId,
    readOutbox(userId).map((item) => (item.id === id ? { ...item, ...changes } : item)),
  )
}

export function removeFromOutbox(userId, id) {
  return writeOutbox(
    userId,
    readOutbox(userId).filter((item) => item.id !== id),
  )
}

// Forget the data the service worker kept for offline viewing (called on logout)
export function clearOfflineData() {
  if ('caches' in window) caches.delete(API_CACHE).catch(() => {})
}
