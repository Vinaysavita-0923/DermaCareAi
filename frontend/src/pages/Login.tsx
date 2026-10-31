import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { extractErrorMessage } from '../services/auth'
import Credits from '../components/Credits'

type Mode = 'login' | 'register'

export default function Login() {
  const [mode, setMode] = useState<Mode>('login')
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const { user, isLoading, login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation() as { state?: { from?: string } }
  const redirectTo = location.state?.from ?? '/dashboard'

  // Already signed in (e.g. a saved session): never show the form again.
  if (!isLoading && user && !submitting) return <Navigate to={redirectTo} replace />

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      if (mode === 'login') {
        await login(email, password)
      } else {
        await register(fullName, email, password)
      }
      navigate(redirectTo, { replace: true })
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <div className="mx-auto max-w-sm">
      <div className="mb-6 flex rounded-lg border border-slate-200 bg-white p-1 text-sm font-medium">
        <button
          type="button"
          onClick={() => { setMode('login'); setError(null) }}
          className={`flex-1 rounded-md py-2 ${mode === 'login' ? 'bg-emerald-600 text-white' : 'text-slate-500'}`}
        >
          Log in
        </button>
        <button
          type="button"
          onClick={() => { setMode('register'); setError(null) }}
          className={`flex-1 rounded-md py-2 ${mode === 'register' ? 'bg-emerald-600 text-white' : 'text-slate-500'}`}
        >
          Sign up
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-6">
        {mode === 'register' && (
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Full name</label>
            <input
              type="text"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none"
            />
          </div>
        )}
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Password</label>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none"
          />
          {mode === 'register' && (
            <p className="mt-1 text-xs text-slate-400">
              At least 8 characters, with a letter and a digit.
            </p>
          )}
        </div>

        {error && (
          <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-emerald-600 py-2.5 font-medium text-white hover:bg-emerald-700 disabled:opacity-60"
        >
          {submitting ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}
        </button>

        <p className="text-center text-xs text-slate-400">
          Google login is planned but not yet connected — see the backend
          README for the exact setup this needs before it can be enabled.
        </p>
      </form>
      </div>

      <Credits />
    </div>
  )
}
