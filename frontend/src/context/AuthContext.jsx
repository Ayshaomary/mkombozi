import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, getTokens, setTokens } from '../lib/api'
import { clearOfflineData } from '../lib/outbox'
import { userCan } from '../lib/permissions'

const AuthContext = createContext(null)

// The logged-in user's details from the last time we were online, so the app opens without internet
const SAVED_USER_KEY = 'mukombozi_user'

function savedUser() {
  try {
    return JSON.parse(localStorage.getItem(SAVED_USER_KEY))
  } catch {
    return null
  }
}

function saveUser(user) {
  try {
    if (user) localStorage.setItem(SAVED_USER_KEY, JSON.stringify(user))
    else localStorage.removeItem(SAVED_USER_KEY)
  } catch {
    // Not saved; the app then needs internet to open next time
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [subscription, setSubscription] = useState(null)
  // True until we know whether a saved login is still valid
  const [loading, setLoading] = useState(() => Boolean(getTokens()))

  const loadSubscription = useCallback(async () => {
    try {
      setSubscription(await api.get('/subscription/'))
    } catch {
      setSubscription(null)
    }
  }, [])

  const refreshUser = useCallback(async () => {
    const me = await api.get('/auth/me/')
    setUser(me)
    saveUser(me)
    return me
  }, [])

  const logout = useCallback(() => {
    // The outbox is kept (it is per user), but the saved pages of data are not
    clearOfflineData()
    saveUser(null)
    setTokens(null)
    setUser(null)
    setSubscription(null)
  }, [])

  // On first load: if a login was saved, check it is still valid
  useEffect(() => {
    if (!getTokens()) return
    refreshUser()
      .then(loadSubscription)
      .catch((err) => {
        // No internet: stay logged in with the saved details instead of logging out
        const saved = err.status === 0 && savedUser()
        if (saved) setUser(saved)
        else logout()
      })
      .finally(() => setLoading(false))
  }, [refreshUser, loadSubscription, logout])

  // The API client fires this when the login has fully expired
  useEffect(() => {
    window.addEventListener('mukombozi:logout', logout)
    return () => window.removeEventListener('mukombozi:logout', logout)
  }, [logout])

  const startSession = async (data) => {
    setTokens({ access: data.access, refresh: data.refresh })
    setUser(data.user)
    saveUser(data.user)
    await loadSubscription()
    return data.user
  }

  const login = async (phone, password) => startSession(await api.post('/auth/login/', { phone, password }))

  const register = async (form) => startSession(await api.post('/auth/register/', form))

  const value = {
    user,
    subscription,
    loading,
    isOwner: user?.role === 'owner',
    // can('products'): what the owner allowed this user (see lib/permissions.js)
    can: (permission) => userCan(user, permission),
    // Admins of the whole platform ("Staff status" in the Django admin) see the admin dashboard
    isAdmin: Boolean(user?.is_staff),
    login,
    register,
    logout,
    refreshUser,
    loadSubscription,
  }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}
