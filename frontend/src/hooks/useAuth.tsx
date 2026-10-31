import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import * as authApi from '../services/auth'
import type { User } from '../services/auth'
import { AUTH_EXPIRED_EVENT } from '../services/api'

interface AuthContextValue {
  user: User | null
  /** true while restoring a session from a stored token on first load —
   * lets the UI show a loading state instead of a flash of "logged out" */
  isLoading: boolean
  /** true after the user chose to log out (vs. a session expiring), so
   * protected pages send them home rather than to the login form */
  loggedOut: boolean
  login: (email: string, password: string) => Promise<void>
  register: (fullName: string, email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

const TOKEN_KEY = 'access_token'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [loggedOut, setLoggedOut] = useState(false)

  // On first load, if a token is already stored (from a previous
  // session), verify it against the REAL backend via /auth/me rather
  // than trusting it blindly — an expired or revoked token is cleared.
  useEffect(() => {
    const existingToken = localStorage.getItem(TOKEN_KEY)
    if (!existingToken) {
      setIsLoading(false)
      return
    }
    authApi
      .fetchMe()
      .then(setUser)
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY)
        setUser(null)
      })
      .finally(() => setIsLoading(false))
  }, [])

  useEffect(() => {
    const onExpired = () => setUser(null)
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired)
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired)
  }, [])

  async function login(email: string, password: string) {
    const result = await authApi.login(email, password)
    localStorage.setItem(TOKEN_KEY, result.access_token)
    setLoggedOut(false)
    setUser(result.user)
  }

  async function register(fullName: string, email: string, password: string) {
    await authApi.register(fullName, email, password)
    // Registration alone doesn't return a token (matches the backend's
    // actual contract — only /login does), so log in right after.
    await login(email, password)
  }

  async function logout() {
    try {
      await authApi.logout()
    } catch {
      // Even if the server call fails (e.g. token already expired),
      // the user must still be logged out locally — never leave them
      // stuck in a state where the UI thinks they're logged in but
      // every request will 401.
    } finally {
      localStorage.removeItem(TOKEN_KEY)
      setLoggedOut(true)
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, loggedOut, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
