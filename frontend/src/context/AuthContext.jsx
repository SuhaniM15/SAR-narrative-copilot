import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'

const AuthContext = createContext(null)
const STORAGE_KEY = 'sar_copilot_auth'

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null)
  const [user, setUser] = useState(null)
  const [bootstrapping, setBootstrapping] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function restore() {
      try {
        const raw = localStorage.getItem(STORAGE_KEY)
        if (!raw) return
        const saved = JSON.parse(raw)
        if (!saved?.token) return
        const me = await api.me(saved.token)
        if (!cancelled) {
          setToken(saved.token)
          setUser(me)
        }
      } catch {
        localStorage.removeItem(STORAGE_KEY)
      } finally {
        if (!cancelled) setBootstrapping(false)
      }
    }
    restore()
    return () => {
      cancelled = true
    }
  }, [])

  const value = useMemo(
    () => ({
      token,
      user,
      bootstrapping,
      async login(email, password) {
        const { access_token } = await api.login(email, password)
        const me = await api.me(access_token)
        setToken(access_token)
        setUser(me)
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ token: access_token }))
        return me
      },
      logout() {
        setToken(null)
        setUser(null)
        localStorage.removeItem(STORAGE_KEY)
      },
      isAnalyst: user?.role === 'analyst' || user?.role === 'admin',
      isReviewer: user?.role === 'reviewer' || user?.role === 'admin',
    }),
    [token, user, bootstrapping],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
