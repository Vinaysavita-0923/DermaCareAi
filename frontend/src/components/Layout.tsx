import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import ConnectionStatus from './ConnectionStatus'
import KashviTour, { START_TOUR_EVENT } from './KashviTour'
import { useAuth } from '../hooks/useAuth'

const ICON_PATHS: Record<string, ReactNode> = {
  dashboard: <path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1v-9.5Z" />,
  analysis: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </>
  ),
  chat: (
    <>
      <path d="M21 11.5a8.5 8.5 0 0 1-12.6 7.4L3 20.5l1.6-5.1A8.5 8.5 0 1 1 21 11.5Z" />
      <path d="M8.5 11.5h.01M12 11.5h.01M15.5 11.5h.01" />
    </>
  ),
  profile: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0 1 16 0" />
    </>
  ),
  routine: (
    <>
      <circle cx="12" cy="13" r="8" />
      <path d="M12 9v4l2.5 2.5M9 2h6" />
    </>
  ),
  products: (
    <>
      <path d="M6 7h12l-1 14H7L6 7Z" />
      <path d="M9 7a3 3 0 0 1 6 0" />
    </>
  ),
  journal: (
    <>
      <path d="M5 4a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4Z" />
      <path d="M9 8h6M9 12h6M9 16h3" />
    </>
  ),
  reports: <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />,
}

function Icon({ name, className = 'h-5 w-5' }: { name: string; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {ICON_PATHS[name]}
    </svg>
  )
}

const SIDEBAR_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: 'dashboard' },
  { to: '/acne-analysis', label: 'Skin Analysis', icon: 'analysis' },
  { to: '/chat', label: 'AI Assistant (Kashvi)', icon: 'chat' },
  { to: '/skin-assessment', label: 'Skin Assessment', icon: 'journal' },
  { to: '/profile', label: 'My Profile', icon: 'profile' },
  { to: '/routines', label: 'Skincare Routine', icon: 'routine' },
  { to: '/products', label: 'Products & Ingredients', icon: 'products' },
  { to: '/journal', label: 'Skin Journal', icon: 'journal' },
  { to: '/reports', label: 'Reports', icon: 'reports' },
]

function Brand() {
  return (
    <NavLink to="/dashboard" className="flex items-center gap-2.5">
      <img src="/logo-small.png" alt="" className="h-11 w-11 rounded-full" />
      <span className="leading-tight">
        <span className="font-display block text-xl text-emerald-900">
          DermaCare <span className="text-emerald-500">AI</span>
        </span>
        <span className="block text-[11px] text-slate-500">Your Personal Skin Companion</span>
      </span>
    </NavLink>
  )
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-20 items-center px-5">
        <Brand />
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-3">
        {SIDEBAR_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            data-tour={item.to}
            onClick={onNavigate}
            className={({ isActive }) =>
              `relative flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-colors ${
                isActive ? 'bg-emerald-100 text-emerald-800' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && <span className="absolute -left-3 top-1.5 bottom-1.5 w-1 rounded-r-full bg-emerald-600" />}
                <Icon name={item.icon} />
                {item.label}
              </>
            )}
          </NavLink>
        ))}
      </nav>
      <p className="border-t border-slate-100 px-5 py-4 text-[11px] leading-snug text-slate-400">
        Educational skin-care information only — not medical advice or a diagnosis.
      </p>
    </div>
  )
}

function GlobalSearch() {
  const navigate = useNavigate()
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const boxRef = useRef<HTMLFormElement>(null)

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    function onClick(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onClick)
    return () => {
      window.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onClick)
    }
  }, [])

  function go(kind: 'kashvi' | 'products') {
    const q = text.trim()
    if (!q) return
    setOpen(false)
    setText('')
    inputRef.current?.blur()
    if (kind === 'kashvi') navigate('/chat', { state: { prefill: q, autoSend: true } })
    else navigate('/products', { state: { q } })
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    go('kashvi')
  }

  const q = text.trim()
  return (
    <form ref={boxRef} onSubmit={onSubmit} className="relative w-full max-w-xl" role="search">
      <svg viewBox="0 0 24 24" className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3.5-3.5" strokeLinecap="round" />
      </svg>
      <input
        ref={inputRef}
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => e.key === 'Escape' && (setOpen(false), inputRef.current?.blur())}
        placeholder="Search for skincare, ingredients, or ask Kashvi…"
        aria-label="Search for skincare, ingredients, or ask Kashvi"
        className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-16 text-sm focus:border-emerald-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-100"
      />
      <kbd className="pointer-events-none absolute right-3 top-1/2 hidden -translate-y-1/2 rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-400 sm:block">
        Ctrl K
      </kbd>
      {open && q && (
        <div className="absolute left-0 right-0 top-full z-30 mt-1.5 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-lg">
          <button type="submit" className="flex w-full items-center gap-3 px-3.5 py-2.5 text-left text-sm hover:bg-emerald-50">
            <Icon name="chat" className="h-4 w-4 text-emerald-600" />
            <span className="truncate">
              Ask Kashvi: <span className="font-medium text-slate-900">“{q}”</span>
            </span>
            <span className="ml-auto text-[10px] text-slate-400">Enter</span>
          </button>
          <button type="button" onClick={() => go('products')} className="flex w-full items-center gap-3 px-3.5 py-2.5 text-left text-sm hover:bg-emerald-50">
            <Icon name="products" className="h-4 w-4 text-emerald-600" />
            <span className="truncate">
              Search products &amp; ingredients for <span className="font-medium text-slate-900">“{q}”</span>
            </span>
          </button>
        </div>
      )}
    </form>
  )
}

function UserMenu() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    window.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      window.removeEventListener('keydown', onKey)
    }
  }, [])

  if (!user) return null
  const name = user.full_name?.trim() || user.email
  const initial = name.charAt(0).toUpperCase()

  // ProtectedRoute sends the user home once `user` clears.
  async function handleLogout() {
    setOpen(false)
    await logout()
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={`flex items-center gap-2.5 rounded-full p-1 pr-2 transition-colors hover:bg-slate-100 ${
          open ? 'bg-slate-100' : ''
        }`}
      >
        <span
          className={`flex h-9 w-9 items-center justify-center rounded-full bg-emerald-600 text-sm font-semibold text-white ring-2 ring-offset-2 transition ${
            open ? 'ring-emerald-500' : 'ring-transparent'
          }`}
        >
          {initial}
        </span>
        <span className="hidden max-w-[10rem] truncate text-sm font-medium text-slate-800 md:block">{name}</span>
        <svg viewBox="0 0 24 24" className={`hidden h-4 w-4 text-slate-500 transition-transform md:block ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" strokeWidth="2">
          <path d="m6 9 6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <div
          role="menu"
          className="anim-fade-in absolute right-0 top-full z-40 mt-2 w-64 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl"
          style={{ animationDuration: '0.15s' }}
        >
          <div className="border-b border-slate-100 px-4 py-3">
            <p className="truncate font-semibold uppercase tracking-wide text-slate-900">{name}</p>
            <p className="truncate text-xs text-slate-500">{user.email}</p>
          </div>
          <div className="py-1">
            <button
              role="menuitem"
              type="button"
              onClick={() => {
                setOpen(false)
                navigate('/profile')
              }}
              className="flex w-full items-center gap-3 px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50"
            >
              <Icon name="profile" className="h-4 w-4" />
              Profile
            </button>
            <button
              role="menuitem"
              type="button"
              onClick={() => {
                setOpen(false)
                window.dispatchEvent(new Event(START_TOUR_EVENT))
              }}
              className="flex w-full items-center gap-3 px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50"
            >
              <Icon name="chat" className="h-4 w-4" />
              Take the tour
            </button>
            <button
              role="menuitem"
              type="button"
              onClick={handleLogout}
              className="flex w-full items-center gap-3 px-4 py-2.5 text-sm font-medium text-rose-600 hover:bg-rose-50"
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l-5-5 5-5M5 12h11" />
              </svg>
              Logout
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function SignedInShell() {
  const location = useLocation()
  const [drawerOpen, setDrawerOpen] = useState(false)

  useEffect(() => setDrawerOpen(false), [location.pathname])

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-slate-200 bg-white lg:block">
        <Sidebar />
      </aside>

      {drawerOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="anim-fade-in absolute inset-0 bg-slate-900/40" onClick={() => setDrawerOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 bg-white shadow-2xl">
            <Sidebar onNavigate={() => setDrawerOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-h-screen flex-col lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/95 px-4 backdrop-blur sm:px-6">
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            aria-label="Open menu"
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <GlobalSearch />
          <div className="ml-auto flex shrink-0 items-center gap-3">
            <span className="hidden sm:block">
              <ConnectionStatus />
            </span>
            <UserMenu />
          </div>
        </header>

        <KashviTour />

        <main className="w-full flex-1 px-4 py-6 sm:px-6 lg:px-8">
          {/* keyed on the path so each page fades in when you navigate */}
          <div key={location.pathname} className="page-enter mx-auto max-w-7xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}

function PublicShell() {
  const location = useLocation()
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-4">
          <NavLink to="/" className="flex items-center gap-2 text-base font-semibold tracking-tight text-emerald-900">
            <img src="/logo-small.png" alt="" className="h-10 w-10 rounded-full" />
            <span className="font-display text-lg font-normal">
              DermaCare <span className="text-emerald-500">AI</span>
            </span>
          </NavLink>
          <div className="ml-auto flex items-center gap-3">
            <ConnectionStatus />
            <NavLink
              to="/login"
              className="whitespace-nowrap rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700"
            >
              Log in
            </NavLink>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:py-10">
        <div key={location.pathname} className="page-enter">
          <Outlet />
        </div>
      </main>
      <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-400">
        Educational skin-care information only — not medical advice or a diagnosis.
      </footer>
    </div>
  )
}

export default function Layout() {
  const { user, isLoading } = useAuth()
  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-400">Loading…</div>
  }
  return user ? <SignedInShell /> : <PublicShell />
}
