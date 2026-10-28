import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, getTokens, setTokens } from '../lib/api'

const AuthContext = createContext(null)

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
    return me
  }, [])

  const logout = useCallback(() => {
    setTokens(null)
    setUser(null)
    setSubscription(null)
  }, [])

  // On first load: if a login was saved, check it is still valid
  useEffect(() => {
    if (!getTokens()) return
    refreshUser()
      .then(loadSubscription)
      .catch(logout)
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
