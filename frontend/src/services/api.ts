/**
 * The one Axios instance the whole app uses to talk to the backend.
 *
 * Base URL comes from VITE_API_BASE_URL (see .env.example) — never
 * hardcoded, so the same build works against a local backend, a
 * staging one, or a deployed one just by changing the env var.
 *
 * The auth token (once login is wired up in a later phase) will be
 * attached here, in one place — not duplicated across every API call.
 */
import axios from 'axios'

export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1'

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
})

// Placeholder for Phase 2 (auth wiring): attach the stored token to
// every outgoing request once login exists. Left as a clear extension
// point rather than guessed at now.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export const AUTH_EXPIRED_EVENT = 'auth:expired'

// A 401 on any call made with a token means the session is over (expired
// or revoked). Clear it and tell AuthProvider, so the app sends the user
// to sign in instead of leaving every page failing silently.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const hadToken = Boolean(error?.config?.headers?.Authorization)
    const isLogin = String(error?.config?.url ?? '').includes('/auth/login')
    if (error?.response?.status === 401 && hadToken && !isLogin) {
      localStorage.removeItem('access_token')
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
    }
    return Promise.reject(error)
  },
)

export interface HealthResponse {
  status: string
  service: string
  environment: string
}

/** Calls the real backend's health endpoint — used by <ConnectionStatus>
 * to prove the frontend and backend actually communicate, not just that
 * the frontend renders. */
export async function fetchHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>('/health')
  return data
}
