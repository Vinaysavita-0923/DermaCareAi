import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, isLoading, loggedOut } = useAuth()
  const location = useLocation()

  if (isLoading) {
    // Avoid a flash-redirect to /login while we're still checking a
    // stored token against the real backend.
    return (
      <div className="flex justify-center py-16 text-slate-400">Loading…</div>
    )
  }

  if (!user) {
    if (loggedOut) return <Navigate to="/" replace />
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return <>{children}</>
}
