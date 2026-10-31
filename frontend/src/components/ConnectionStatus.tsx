import { useEffect, useState } from 'react'
import { fetchHealth, API_BASE_URL } from '../services/api'

type Status = 'checking' | 'connected' | 'unreachable'

/**
 * Calls the real GET /api/v1/health endpoint and shows what actually
 * comes back — nothing is mocked. If the backend isn't running this
 * honestly shows "offline", not a faked "connected". The full detail
 * lives in the tooltip so the header stays compact.
 */
export default function ConnectionStatus() {
  const [status, setStatus] = useState<Status>('checking')
  const [detail, setDetail] = useState<string>('')

  useEffect(() => {
    let cancelled = false
    fetchHealth()
      .then((data) => {
        if (cancelled) return
        setStatus('connected')
        setDetail(`${data.service} · ${data.environment}`)
      })
      .catch((err) => {
        if (cancelled) return
        setStatus('unreachable')
        setDetail(err instanceof Error ? err.message : 'Unknown error')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const dotClass =
    status === 'connected'
      ? 'bg-emerald-500'
      : status === 'unreachable'
        ? 'bg-rose-500'
        : 'bg-amber-400 animate-pulse'

  const label =
    status === 'connected' ? 'Online' : status === 'unreachable' ? 'Offline' : 'Checking'

  return (
    <div
      className="flex items-center gap-1.5 whitespace-nowrap rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600"
      title={`Backend ${label.toLowerCase()}${detail ? ` — ${detail}` : ''} (${API_BASE_URL})`}
    >
      <span className={`h-2 w-2 rounded-full ${dotClass}`} aria-hidden="true" />
      {label}
    </div>
  )
}
