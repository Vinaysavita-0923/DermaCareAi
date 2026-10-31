/**
 * Auth API calls, typed to match the backend's real schemas exactly
 * (app/schemas/auth_schema.py) — verified against the live backend's
 * actual responses, not guessed from the OpenAPI shape alone.
 */
import axios from 'axios'
import { api } from './api'

export interface User {
  id: number
  email: string
  full_name: string | null
  is_active: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_at: string
  user: User
}

export async function register(fullName: string, email: string, password: string): Promise<User> {
  const { data } = await api.post<User>('/auth/register', {
    full_name: fullName,
    email,
    password,
  })
  return data
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>('/auth/login', { email, password })
  return data
}

export async function fetchMe(): Promise<User> {
  const { data } = await api.get<User>('/auth/me')
  return data
}

export async function logout(): Promise<void> {
  await api.post('/auth/logout')
}

/**
 * FastAPI returns errors in TWO different shapes, confirmed against
 * the real running backend:
 *   - 401 / 409 (our own HTTPException calls): {"detail": "a plain string"}
 *   - 422 (Pydantic validation, e.g. weak password, bad email):
 *       {"detail": [{"loc": [...], "msg": "...", "type": "..."}]}
 * This turns either shape into one plain string for the UI, instead of
 * every form guessing at the shape itself.
 */
export function extractErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length > 0) {
      // Pydantic's msg is often prefixed "Value error, " — strip that
      // for a cleaner user-facing message.
      return detail
        .map((d: { msg?: string }) => (d.msg ?? '').replace(/^Value error,\s*/, ''))
        .filter(Boolean)
        .join(' ')
    }
    if (err.code === 'ECONNABORTED' || err.message === 'Network Error') {
      return 'Could not reach the server. Please check your connection and try again.'
    }
  }
  return 'Something went wrong. Please try again.'
}
