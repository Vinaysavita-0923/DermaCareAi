import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { getMyProfile, DATASET_CONCERNS, type SkinProfile } from '../services/profile'
import { getReportSummary, type ReportSummary } from '../services/reports'
import { getAssessmentHistory, type AssessmentHistoryEntry } from '../services/assessment'
import { listRoutines, logRoutineDay, type Routine } from '../services/routines'
import { getRecommendations } from '../services/recommendations'
import { getProduct } from '../services/products'
import { extractErrorMessage } from '../services/auth'

const TIPS = [
  'Use a broad-spectrum sunscreen (SPF 30+) every morning, even on cloudy days — UV rays still reach your skin.',
  'Introduce one new active ingredient at a time and patch test it first, so you know what your skin reacts to.',
  'Cleanse gently: lukewarm water and a mild cleanser protect your skin barrier better than hot water and scrubbing.',
  'Apply moisturiser on slightly damp skin to help lock in hydration.',
  'Change your pillowcase a couple of times a week — it collects oil, sweat and bacteria.',
]

const ICONS: Record<string, ReactNode> = {
  camera: (
    <>
      <path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z" />
      <circle cx="12" cy="13.5" r="3.5" />
    </>
  ),
  chat: (
    <>
      <path d="M21 11.5a8.5 8.5 0 0 1-12.6 7.4L3 20.5l1.6-5.1A8.5 8.5 0 1 1 21 11.5Z" />
      <path d="M8.5 11.5h.01M12 11.5h.01M15.5 11.5h.01" />
    </>
  ),
  calendar: (
    <>
      <rect x="3.5" y="5" width="17" height="15.5" rx="2" />
      <path d="M3.5 10h17M8 3v4M16 3v4" />
    </>
  ),
  chart: <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />,
  clipboard: (
    <>
      <rect x="5" y="4" width="14" height="17" rx="2" />
      <path d="M9 4V3h6v1M9 10h6M9 14h6M9 18h3" />
    </>
  ),
  bag: (
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
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </>
  ),
  moon: <path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z" />,
  check: <path d="m5 12.5 4.5 4.5L19 7.5" />,
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 8h.01" />
    </>
  ),
}

function Icon({ name, className = 'h-5 w-5' }: { name: string; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {ICONS[name]}
    </svg>
  )
}

function todayISO(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function concernLabel(tag: string): string {
  return DATASET_CONCERNS.find((c) => c.tag === tag)?.label ?? tag.replace(/_/g, ' ').replace(/^\w/, (m) => m.toUpperCase())
}

function Card({ title, action, children, className = '' }: { title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-slate-200 bg-white p-5 shadow-sm ${className}`}>
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          {title && <h2 className="text-base font-semibold text-slate-900">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

function CardLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="inline-flex shrink-0 items-center gap-1 text-sm font-medium text-emerald-700 hover:text-emerald-900">
      {children}
      <Icon name="arrow" className="h-4 w-4" />
    </Link>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const [profile, setProfile] = useState<SkinProfile | null>(null)
  const [report, setReport] = useState<ReportSummary | null>(null)
  const [history, setHistory] = useState<AssessmentHistoryEntry[]>([])
  const [routines, setRoutines] = useState<Routine[]>([])
  const [recommendedCount, setRecommendedCount] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      getMyProfile(),
      getReportSummary(30),
      getAssessmentHistory(100).catch(() => []),
      listRoutines().catch(() => []),
    ])
      .then(([p, r, h, rt]) => {
        setProfile(p)
        setReport(r)
        setHistory(h)
        setRoutines(rt)
        if (p) {
          getRecommendations()
            .then((rec) => setRecommendedCount(rec.matches.length))
            .catch(() => setRecommendedCount(null))
        }
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  const name = user?.full_name?.trim() || user?.email || ''
  const latest = history[0] ?? null
  const now = new Date()
  const thisMonth = history.filter((h) => {
    const d = new Date(h.created_at)
    return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth()
  }).length
  const routineTypes = [...new Set(routines.map((r) => r.routine_type))]

  return (
    <div className="space-y-5">
      {error && (
        <p className="rounded-xl bg-rose-50 px-4 py-2.5 text-sm text-rose-700" role="alert">
          {error}
        </p>
      )}

      {/* Welcome + tip */}
      <div className="grid gap-5 xl:grid-cols-3">
        <section className="anim-fade-up flex items-center gap-6 overflow-hidden rounded-2xl border border-emerald-100 bg-gradient-to-br from-emerald-100 via-emerald-50 to-amber-50 p-6 sm:p-8 xl:col-span-2">
          <div className="min-w-0 flex-1">
            <p className="text-base font-medium text-slate-700">Welcome back,</p>
            <h1 className="mt-0.5 text-3xl font-bold tracking-tight text-emerald-950 sm:text-4xl">{name}!</h1>
            <p className="mt-2 text-slate-600">Let's take care of your skin today.</p>
            <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                { to: '/acne-analysis', label: 'New Skin Analysis', icon: 'camera', primary: true },
                { to: '/chat', label: 'Ask Kashvi', icon: 'chat' },
                { to: '/routines', label: 'My Routine', icon: 'calendar' },
                { to: '/reports', label: 'View Reports', icon: 'chart' },
              ].map((a) => (
                <Link
                  key={a.to}
                  to={a.to}
                  className={`flex flex-col items-center justify-center gap-2 rounded-xl px-2 py-3.5 text-center text-xs font-medium shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${
                    a.primary ? 'bg-emerald-700 text-white hover:bg-emerald-800' : 'bg-white/90 text-emerald-800 hover:bg-white'
                  }`}
                >
                  <Icon name={a.icon} className="h-6 w-6" />
                  {a.label}
                </Link>
              ))}
            </div>
          </div>
          <div className="hidden shrink-0 flex-col items-center text-center md:flex">
            <img src="/logo.png" alt="" className="anim-float h-40 w-40 lg:h-44 lg:w-44" />
            <p className="mt-3 font-serif text-lg leading-snug text-emerald-900">
              Healthier Skin,
              <br />
              Happier You.
            </p>
            <span className="mt-2 h-0.5 w-10 rounded-full bg-emerald-600" />
          </div>
        </section>

        <TipCard />
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          to="/skin-assessment"
          icon="camera"
          label="Skin Assessments"
          value={loading ? '–' : history.length}
          sub={
            thisMonth > 0 ? (
              <span className="text-emerald-700">↑ {thisMonth} this month</span>
            ) : (
              'None yet this month'
            )
          }
        />
        <StatCard
          to="/routines"
          icon="calendar"
          label="Active Routines"
          value={loading ? '–' : routines.length}
          sub={routineTypes.length ? routineTypes.map((t) => (t === 'night' ? 'Night' : 'Morning')).join(' & ') : 'Create your first routine'}
        />
        <StatCard
          to="/skin-assessment"
          state={profile ? { view: 'products' } : undefined}
          icon="bag"
          label="Recommended Products"
          value={loading ? '–' : recommendedCount ?? '–'}
          sub={profile ? 'Personalised for you' : 'Complete your assessment'}
        />
        <StatCard
          to="/journal"
          icon="journal"
          label="Journal Entries"
          value={loading ? '–' : report?.journal_entry_count ?? 0}
          sub="Last 30 days"
        />
      </div>

      {/* Latest assessment · consistency · profile */}
      <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-3">
        <Card title="Latest Skin Assessment" action={<CardLink to="/skin-assessment">View all</CardLink>}>
          {latest ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-semibold text-slate-900">Assessment result</p>
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
                  <Icon name="check" className="h-3.5 w-3.5" /> Completed
                </span>
              </div>
              <p className="mt-1 text-sm text-slate-500">
                {new Date(latest.created_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}
                {' • '}
                {new Date(latest.created_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <span className="rounded-full bg-sky-50 px-3 py-1 text-sm font-medium capitalize text-sky-700">
                  {latest.skin_type} skin
                </span>
                {latest.is_sensitive && (
                  <span className="rounded-full bg-amber-50 px-3 py-1 text-sm font-medium text-amber-700">Sensitive</span>
                )}
                {(latest.concerns ?? []).slice(0, 4).map((c) => (
                  <span key={c} className="rounded-full bg-rose-50 px-3 py-1 text-sm font-medium text-rose-700">
                    {concernLabel(c)}
                  </span>
                ))}
              </div>
              <Link
                to="/skin-assessment"
                state={{ view: 'report' }}
                className="mt-5 flex items-center justify-center gap-2 rounded-xl bg-emerald-700 py-3 text-sm font-medium text-white hover:bg-emerald-800"
              >
                View Detailed Report <Icon name="arrow" className="h-4 w-4" />
              </Link>
            </>
          ) : (
            <EmptyState text="You haven't taken a skin assessment yet." cta="Take the assessment" to="/skin-assessment" loading={loading} />
          )}
        </Card>

        <ConsistencyCard report={report} loading={loading} />

        <Card title="Your Skin Profile" action={<CardLink to="/skin-assessment">Update</CardLink>} className="lg:col-span-2 xl:col-span-1">
          {profile ? (
            <dl className="space-y-2.5">
              {[
                { label: 'Skin type', value: `${profile.skin_type}${profile.skin_subtype ? ` · ${profile.skin_subtype}` : ''}`, tone: 'bg-sky-50' },
                { label: 'Age group', value: profile.age_group ?? 'Not set', tone: 'bg-violet-50' },
                {
                  label: 'Sensitivity',
                  value: profile.is_sensitive === true ? 'Sensitive' : profile.is_sensitive === false ? 'Not sensitive' : 'Not sure',
                  tone: 'bg-amber-50',
                },
                {
                  label: 'Concerns',
                  value: profile.concerns?.length ? profile.concerns.map(concernLabel).join(', ') : 'None selected',
                  tone: 'bg-emerald-50',
                },
              ].map((row) => (
                <div key={row.label} className={`flex items-start justify-between gap-3 rounded-xl px-3.5 py-2.5 ${row.tone}`}>
                  <dt className="shrink-0 text-sm text-slate-500">{row.label}</dt>
                  <dd className="text-right text-sm font-semibold capitalize text-slate-800">{row.value}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <EmptyState text="Set up your skin profile to personalise everything." cta="Create profile" to="/skin-assessment" loading={loading} />
          )}
        </Card>
      </div>

      {/* Chart + routine */}
      <div className="grid gap-5 xl:grid-cols-2">
        <Card title="How Your Skin Felt" action={<CardLink to="/journal">Open journal</CardLink>}>
          <FeelingChart counts={report?.feeling_tag_counts ?? {}} loading={loading} />
        </Card>
        <RoutineCard routines={routines} loading={loading} />
      </div>

      {report && <p className="text-xs text-slate-400">{report.disclaimer}</p>}
    </div>
  )
}

function StatCard({
  to,
  state,
  icon,
  label,
  value,
  sub,
}: {
  to: string
  state?: object
  icon: string
  label: string
  value: ReactNode
  sub: ReactNode
}) {
  return (
    <Link to={to} state={state} className="group flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
      <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700">
        <Icon name={icon} className="h-7 w-7" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center justify-between text-sm text-slate-500">
          {label}
          <span className="text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-emerald-600">›</span>
        </span>
        <span className="block text-2xl font-bold text-slate-900">{value}</span>
        <span className="block truncate text-xs text-slate-500">{sub}</span>
      </span>
    </Link>
  )
}

function EmptyState({ text, cta, to, loading }: { text: string; cta: string; to: string; loading: boolean }) {
  if (loading) return <p className="py-6 text-center text-sm text-slate-400">Loading…</p>
  return (
    <div className="rounded-xl border border-dashed border-slate-200 p-5 text-center">
      <p className="text-sm text-slate-500">{text}</p>
      <Link to={to} className="mt-3 inline-block rounded-full bg-emerald-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-emerald-700">
        {cta}
      </Link>
    </div>
  )
}

function TipCard() {
  const start = Math.floor(Date.now() / 86_400_000) % TIPS.length
  const [i, setI] = useState(start)
  const step = (d: number) => setI((v) => (v + d + TIPS.length) % TIPS.length)
  return (
    <section className="anim-fade-up rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" style={{ ['--d' as string]: '0.08s' }}>
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
          Today's Tip <Icon name="sun" className="h-5 w-5 text-amber-500" />
        </h2>
        <div className="flex gap-1">
          <button type="button" onClick={() => step(-1)} aria-label="Previous tip" className="rounded-full p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
            ‹
          </button>
          <button type="button" onClick={() => step(1)} aria-label="Next tip" className="rounded-full p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
            ›
          </button>
        </div>
      </div>
      <div key={i} className="anim-fade-in mt-4 flex gap-4 rounded-xl bg-amber-50 p-4">
        <Icon name="sun" className="h-10 w-10 shrink-0 text-amber-500" />
        <p className="text-sm leading-relaxed text-slate-700">{TIPS[i]}</p>
      </div>
      <div className="mt-5 flex items-center gap-3">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
          <div className="h-full rounded-full bg-emerald-600 transition-all" style={{ width: `${((i + 1) / TIPS.length) * 100}%` }} />
        </div>
        <span className="text-xs text-slate-500">
          {i + 1}/{TIPS.length}
        </span>
      </div>
    </section>
  )
}

function ConsistencyCard({ report, loading }: { report: ReportSummary | null; loading: boolean }) {
  const stats = report?.routine_completion ?? []
  const logged = stats.reduce((s, r) => s + r.days_logged, 0)
  const done = stats.reduce((s, r) => s + r.days_completed, 0)
  const score = logged ? Math.round((done / logged) * 100) : null
  const level =
    score === null ? null : score >= 70 ? { label: 'Great', cls: 'bg-emerald-50 text-emerald-700' } : score >= 40 ? { label: 'Fair', cls: 'bg-amber-50 text-amber-700' } : { label: 'Needs work', cls: 'bg-rose-50 text-rose-700' }
  const r = 52
  const c = 2 * Math.PI * r

  return (
    <Card
      title={
        <span className="flex items-center gap-1.5">
          Routine Consistency
          <span title="Share of the routine days you logged in the last 30 days that you marked as completed." className="text-slate-400">
            <Icon name="info" className="h-4 w-4" />
          </span>
        </span>
      }
    >
      {loading ? (
        <p className="py-6 text-center text-sm text-slate-400">Loading…</p>
      ) : score === null ? (
        <EmptyState text="Log your routine for a few days to see your consistency score." cta="Go to routines" to="/routines" loading={false} />
      ) : (
        <div className="flex items-center gap-5">
          <div className="relative h-32 w-32 shrink-0">
            <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
              <circle cx="60" cy="60" r={r} fill="none" stroke="#e2eedb" strokeWidth="10" />
              <circle
                cx="60"
                cy="60"
                r={r}
                fill="none"
                stroke="#3f7a45"
                strokeWidth="10"
                strokeLinecap="round"
                strokeDasharray={c}
                strokeDashoffset={c * (1 - score / 100)}
                style={{ transition: 'stroke-dashoffset 0.9s ease-out' }}
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-3xl font-bold text-slate-900">{score}</span>
              <span className="text-xs text-slate-400">/ 100</span>
            </div>
          </div>
          <div className="min-w-0">
            {level && <span className={`inline-block rounded-full px-2.5 py-0.5 text-sm font-semibold ${level.cls}`}>{level.label}</span>}
            <p className="mt-2 text-sm leading-relaxed text-slate-600">
              You completed {done} of the {logged} routine day{logged === 1 ? '' : 's'} you logged in the last 30 days.
            </p>
            <Link to="/reports" className="mt-3 inline-flex items-center gap-1 rounded-full border border-emerald-200 px-3 py-1.5 text-sm font-medium text-emerald-700 hover:bg-emerald-50">
              View progress <Icon name="arrow" className="h-4 w-4" />
            </Link>
          </div>
        </div>
      )}
    </Card>
  )
}

function FeelingChart({ counts, loading }: { counts: Record<string, number>; loading: boolean }) {
  const entries = Object.entries(counts)
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
  if (loading) return <p className="py-10 text-center text-sm text-slate-400">Loading…</p>
  if (!entries.length) {
    return <EmptyState text="No journal entries in the last 30 days. Log how your skin feels to see patterns here." cta="Write a journal entry" to="/journal" loading={false} />
  }
  const max = Math.max(...entries.map(([, n]) => n))
  const ticks = max <= 1 ? [0, 1] : [0, Math.ceil(max / 2), max]
  const label = (t: string) => t.replace(/_/g, ' ').replace(/^\w/, (m) => m.toUpperCase())

  return (
    <figure>
      <figcaption className="mb-3 text-xs text-slate-500">Times each feeling was logged · last 30 days</figcaption>
      <div className="flex gap-2">
        <div className="relative h-44 w-6 shrink-0 text-right text-[10px] text-slate-400" aria-hidden="true">
          {ticks.map((t) => (
            <span key={t} className="absolute right-0" style={{ bottom: `${(t / max) * 100}%`, transform: 'translateY(50%)' }}>
              {t}
            </span>
          ))}
        </div>
        <div className="relative flex-1">
          <div className="absolute inset-x-0 top-0 h-44" aria-hidden="true">
            {ticks.map((t) => (
              <div key={t} className="absolute inset-x-0 border-t border-slate-100" style={{ bottom: `${(t / max) * 100}%` }} />
            ))}
          </div>
          <div className="relative flex h-44 items-end gap-2" aria-hidden="true">
            {entries.map(([tag, n]) => (
              <div key={tag} className="group relative flex h-full flex-1 items-end justify-center">
                <div
                  className="w-full max-w-10 rounded-t bg-emerald-500 transition-colors group-hover:bg-emerald-700"
                  style={{ height: `${(n / max) * 100}%` }}
                />
                <span className="pointer-events-none absolute bottom-full mb-1 hidden whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-[11px] text-white shadow group-hover:block" style={{ bottom: `${(n / max) * 100}%` }}>
                  {label(tag)}: {n} {n === 1 ? 'time' : 'times'}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-2 flex gap-2" aria-hidden="true">
            {entries.map(([tag]) => (
              <span key={tag} className="flex-1 truncate text-center text-[11px] text-slate-500" title={label(tag)}>
                {label(tag)}
              </span>
            ))}
          </div>
        </div>
      </div>
      <table className="sr-only">
        <caption>Times each skin feeling was logged in the last 30 days</caption>
        <tbody>
          {entries.map(([tag, n]) => (
            <tr key={tag}>
              <th scope="row">{label(tag)}</th>
              <td>{n}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  )
}

function RoutineCard({ routines, loading }: { routines: Routine[]; loading: boolean }) {
  const [activeId, setActiveId] = useState<number | null>(null)
  const [names, setNames] = useState<Record<number, string>>({})
  const [doneToday, setDoneToday] = useState<Record<number, boolean>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const sorted = [...routines].sort((a, b) => (a.routine_type === 'morning' ? -1 : 1) - (b.routine_type === 'morning' ? -1 : 1))
  const routine = sorted.find((r) => r.id === activeId) ?? sorted[0] ?? null

  useEffect(() => {
    const ids = [...new Set(routines.flatMap((r) => r.items.map((i) => i.product_id)).filter((id): id is number => id !== null))]
    Promise.all(ids.map((id) => getProduct(id).then((p) => [id, p.name] as const).catch(() => null))).then((pairs) =>
      setNames(Object.fromEntries(pairs.filter((p): p is readonly [number, string] => p !== null))),
    )
  }, [routines])

  async function markDone() {
    if (!routine) return
    setSaving(true)
    setError(null)
    try {
      await logRoutineDay(routine.id, todayISO(), true)
      setDoneToday((d) => ({ ...d, [routine.id]: true }))
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const steps = routine ? [...routine.items].sort((a, b) => a.step_order - b.step_order) : []

  return (
    <Card
      title="Your Skincare Routine"
      action={
        <div className="flex items-center gap-3">
          {sorted.length > 1 && (
            <div className="flex rounded-full bg-slate-100 p-0.5 text-xs font-medium">
              {sorted.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => setActiveId(r.id)}
                  className={`flex items-center gap-1 rounded-full px-2.5 py-1 capitalize ${routine?.id === r.id ? 'bg-white text-emerald-800 shadow-sm' : 'text-slate-500'}`}
                >
                  <Icon name={r.routine_type === 'night' ? 'moon' : 'sun'} className="h-3.5 w-3.5" />
                  {r.routine_type}
                </button>
              ))}
            </div>
          )}
          <CardLink to="/routines">View routine</CardLink>
        </div>
      }
    >
      {loading ? (
        <p className="py-6 text-center text-sm text-slate-400">Loading…</p>
      ) : !routine ? (
        <EmptyState text="You don't have a routine yet. Build one in a minute." cta="Create a routine" to="/routines" loading={false} />
      ) : (
        <>
          <ol className="flex items-start gap-1 overflow-x-auto pb-2">
            {steps.map((s, idx) => (
              <li key={s.id} className="flex items-start">
                <div className="flex w-24 flex-col items-center text-center">
                  <span className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-50 text-sm font-bold text-emerald-700 ring-1 ring-emerald-100">
                    {idx + 1}
                  </span>
                  <span className="mt-2 line-clamp-2 text-xs font-semibold text-slate-800">
                    {(s.product_id !== null && names[s.product_id]) || s.notes || `Step ${idx + 1}`}
                  </span>
                  {s.product_id !== null && names[s.product_id] && s.notes && (
                    <span className="mt-0.5 line-clamp-1 text-[11px] text-slate-400">{s.notes}</span>
                  )}
                </div>
                {idx < steps.length - 1 && <span className="mt-3 px-0.5 text-slate-300">›</span>}
              </li>
            ))}
          </ol>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-emerald-50 px-4 py-3">
            <p className="flex items-center gap-2 text-sm text-emerald-900">
              {doneToday[routine.id] ? (
                <>
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-600 text-white">
                    <Icon name="check" className="h-3.5 w-3.5" />
                  </span>
                  Today's {routine.routine_type} routine is marked as done.
                </>
              ) : (
                <>Finished all {steps.length} steps of your {routine.routine_type} routine today?</>
              )}
            </p>
            {!doneToday[routine.id] && (
              <button
                type="button"
                onClick={markDone}
                disabled={saving}
                className="inline-flex items-center gap-1.5 rounded-full border border-emerald-600 bg-white px-3.5 py-1.5 text-sm font-medium text-emerald-700 hover:bg-emerald-600 hover:text-white disabled:opacity-50"
              >
                <Icon name="check" className="h-4 w-4" /> {saving ? 'Saving…' : 'Mark as done'}
              </button>
            )}
          </div>
          {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}
        </>
      )}
    </Card>
  )
}
