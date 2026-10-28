import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { NETWORK_EVENT, api, lastServerReachable } from '../lib/api'
import {
  OUTBOX_CHANGED,
  addToOutbox,
  readOutbox,
  removeFromOutbox,
  updateOutboxItem,
} from '../lib/outbox'
import { useAuth } from './AuthContext'

const OfflineContext = createContext(null)

const PATHS = { sale: '/sales/', expense: '/expenses/' }
// While records are waiting, try sending them this often
const RETRY_EVERY_MS = 30 * 1000
// While offline, check this often whether the server can be reached again
const CHECK_EVERY_MS = 15 * 1000

// Knows whether the phone is online, and sends waiting sales and expenses as soon as it can
export function OfflineProvider({ children }) {
  const { user } = useAuth()
  const userId = user.id
  const [browserOnline, setBrowserOnline] = useState(() => navigator.onLine)
  const [serverReachable, setServerReachable] = useState(lastServerReachable)
  const online = browserOnline && serverReachable
  const [items, setItems] = useState(() => readOutbox(userId))
  const [syncing, setSyncing] = useState(false)
  const syncingRef = useRef(false)

  useEffect(() => {
    const update = () => setBrowserOnline(navigator.onLine)
    const onNetwork = (event) => setServerReachable(event.detail.online)
    window.addEventListener('online', update)
    window.addEventListener('offline', update)
    window.addEventListener(NETWORK_EVENT, onNetwork)
    return () => {
      window.removeEventListener('online', update)
      window.removeEventListener('offline', update)
      window.removeEventListener(NETWORK_EVENT, onNetwork)
    }
  }, [])

  // While offline, a small request now and then tells us when the server answers again
  useEffect(() => {
    if (online || !browserOnline) return
    const check = () => api.get('/subscription/plans/').catch(() => {})
    const timer = setInterval(check, CHECK_EVERY_MS)
    return () => clearInterval(timer)
  }, [online, browserOnline])

  useEffect(() => {
    const reload = () => setItems(readOutbox(userId))
    window.addEventListener(OUTBOX_CHANGED, reload)
    // Another tab of the app changed the outbox
    window.addEventListener('storage', reload)
    return () => {
      window.removeEventListener(OUTBOX_CHANGED, reload)
      window.removeEventListener('storage', reload)
    }
  }, [userId])

  const sync = useCallback(async () => {
    if (syncingRef.current) return
    syncingRef.current = true
    setSyncing(true)
    try {
      for (const item of readOutbox(userId)) {
        if (item.status === 'failed') continue // waits until the user taps "Try again"
        try {
          await api.post(PATHS[item.kind], item.body)
          removeFromOutbox(userId, item.id)
        } catch (err) {
          // No internet, server trouble or login expired: stop and try again later
          if (err.status === 0 || err.status === 401 || err.status >= 500) break
          // The server refused it (e.g. product deleted, subscription ended): the user decides
          updateOutboxItem(userId, item.id, { status: 'failed', error: err.message })
        }
      }
    } finally {
      syncingRef.current = false
      setSyncing(false)
    }
  }, [userId])

  const waitingCount = items.filter((item) => item.status === 'waiting').length

  // Send when the app opens, when the internet comes back, and every 30 seconds while waiting
  useEffect(() => {
    if (online && waitingCount > 0) sync()
  }, [online, waitingCount, sync])

  useEffect(() => {
    if (!online || waitingCount === 0) return
    const timer = setInterval(sync, RETRY_EVERY_MS)
    return () => clearInterval(timer)
  }, [online, waitingCount, sync])

  const value = {
    online,
    items,
    syncing,
    sync,
    waitingCount,
    failedCount: items.length - waitingCount,
    save: (item) => addToOutbox(userId, { created_at: new Date().toISOString(), ...item }),
    retry: (id) => {
      updateOutboxItem(userId, id, { status: 'waiting', error: null })
      sync()
    },
    discard: (id) => removeFromOutbox(userId, id),
  }
  return <OfflineContext.Provider value={value}>{children}</OfflineContext.Provider>
}

export function useOffline() {
  return useContext(OfflineContext)
}
