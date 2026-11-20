import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { analyzeAcneImage, type AcneAnalysisResult } from '../services/acne'
import { analyzeSkinCondition, type SkinConditionResult } from '../services/skinCondition'
import { extractErrorMessage } from '../services/auth'
import PageHeader from '../components/PageHeader'

// Donut colours: greens for everyday conditions, rose for serious ones,
// slate for the leftover "Other" slice — so the warning reads at a glance.
const SAFE_COLORS = ['#3f7a45', '#78a869', '#a0c491']
const SERIOUS_COLORS = ['#e11d48', '#fb7185', '#fda4af']
const OTHER_COLOR = '#cbd5e1'

// Resolve once at least `ms` have passed since `started`.
function holdFor(started: number, ms: number): Promise<void> {
  const left = ms - (Date.now() - started)
  return left > 0 ? new Promise((r) => setTimeout(r, left)) : Promise.resolve()
}

const MAX_MB = 8 // matches the backend's acne_max_image_mb default
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp']

type Mode = 'condition' | 'acne'

export default function AcneAnalysis() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<Mode>('condition')
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [acneResult, setAcneResult] = useState<AcneAnalysisResult | null>(null)
  const [condResult, setCondResult] = useState<SkinConditionResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    }
  }, [previewUrl])

  function resetResults() {
    setAcneResult(null)
    setCondResult(null)
    setError(null)
  }

  function switchMode(next: Mode) {
    if (next === mode) return
    setMode(next)
    resetResults()
  }

  function handleSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = e.target.files?.[0] ?? null
    resetResults()
    if (!picked) {
      setFile(null)
      setPreviewUrl(null)
      return
    }
    if (!ALLOWED_TYPES.includes(picked.type)) {
      setError('Please choose a JPEG, PNG or WebP image.')
      setFile(null)
      setPreviewUrl(null)
      return
    }
    if (picked.size > MAX_MB * 1024 * 1024) {
      setError(`Image is too large. Maximum size is ${MAX_MB} MB.`)
      setFile(null)
      setPreviewUrl(null)
      return
    }
    setFile(picked)
    setPreviewUrl(URL.createObjectURL(picked))
  }

  async function handleAnalyze() {
    if (!file) return
    setLoading(true)
    resetResults()
    const started = Date.now()
    // Keep the scan running for at least this long so the animation reads
    // as "scanning the image" even when the model answers faster.
    const MIN_SCAN_MS = 5000
    try {
      if (mode === 'acne') {
        const res = await analyzeAcneImage(file)
        await holdFor(started, MIN_SCAN_MS)
        setAcneResult(res)
      } else {
        const res = await analyzeSkinCondition(file)
        await holdFor(started, MIN_SCAN_MS)
        setCondResult(res)
      }
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Skin Analysis (Experimental)"
        intro="Upload a clear, well-lit photo of the skin area. Images are analysed in memory and never stored."
      />

      {/* Mode switch */}
      <div className="inline-flex rounded-xl border border-slate-200 bg-white p-1">
        <button
          onClick={() => switchMode('condition')}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
            mode === 'condition' ? 'bg-emerald-600 text-white' : 'text-slate-600 hover:bg-slate-50'
          }`}
        >
          Skin Condition Check
        </button>
        <button
          onClick={() => switchMode('acne')}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
            mode === 'acne' ? 'bg-emerald-600 text-white' : 'text-slate-600 hover:bg-slate-50'
          }`}
        >
          Acne Check
        </button>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
          <input
            type="file"
            accept={ALLOWED_TYPES.join(',')}
            onChange={handleSelect}
            className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-emerald-600 file:px-3 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-emerald-700"
          />
          {previewUrl && (
            <div className="relative overflow-hidden rounded-md">
              <img
                src={previewUrl}
                alt="Selected upload preview"
                className="max-h-72 w-full rounded-md object-contain"
              />
              {loading && (
                <div className="scan-overlay pointer-events-none absolute inset-0" aria-hidden="true">
                  <span className="scan-line" />
                  <span className="scan-corner left-2 top-2 border-l-2 border-t-2" />
                  <span className="scan-corner right-2 top-2 border-r-2 border-t-2" />
                  <span className="scan-corner bottom-2 left-2 border-b-2 border-l-2" />
                  <span className="scan-corner bottom-2 right-2 border-b-2 border-r-2" />
                  <span className="scan-label">Scanning…</span>
                </div>
              )}
            </div>
          )}
          <button
            onClick={handleAnalyze}
            disabled={!file || loading}
            className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {loading ? 'Analysing…' : 'Analyse image'}
          </button>
          {error && (
            <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
              {error}
            </p>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-sm font-medium text-slate-700">Result</h2>
          {mode === 'condition' ? (
            <ConditionResult result={condResult} loading={loading} navigate={navigate} />
          ) : (
            <AcneResult result={acneResult} navigate={navigate} />
          )}
        </div>
      </div>
    </div>
  )
}

function ConditionResult({
  result,
  loading,
  navigate,
}: {
  result: SkinConditionResult | null
  loading: boolean
  navigate: ReturnType<typeof useNavigate>
}) {
  if (loading) return <p className="mt-2 text-sm text-slate-400">Analysing…</p>
  if (!result) return <p className="mt-2 text-sm text-slate-400">No analysis yet.</p>

  if (result.model_status === 'model_not_configured') {
    return (
      <div className="mt-2 space-y-2 text-sm">
        <p className="font-medium text-slate-800">Analysis model not available</p>
        <p className="text-xs text-slate-400">{result.note}</p>
      </div>
    )
  }

  // The image didn't look like skin, so there's no prediction to show.
  if (result.not_skin || result.predictions.length === 0) {
    return (
      <div className="mt-3 space-y-2">
        <div className="flex items-center gap-2 text-slate-800">
          <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0 text-amber-500" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="9" />
            <path d="M12 8v5M12 16.5v.5" strokeLinecap="round" />
          </svg>
          <p className="font-semibold">That doesn't look like a skin photo</p>
        </div>
        <p className="rounded-lg bg-amber-50 px-3 py-2.5 text-sm text-amber-800">{result.note}</p>
      </div>
    )
  }

  const top = result.predictions[0]

  // Colour each guess (serious -> rose), then add an honest "Other" slice
  // for the probability the model spread across the remaining conditions,
  // so the ring always sums to 100% without pretending the top 3 do.
  let safe = 0
  let serious = 0
  const slices = result.predictions.map((g) => ({
    label: g.label,
    value: g.score * 100,
    serious: g.serious,
    color: g.serious ? SERIOUS_COLORS[serious++ % SERIOUS_COLORS.length] : SAFE_COLORS[safe++ % SAFE_COLORS.length],
  }))
  const shown = slices.reduce((s, d) => s + d.value, 0)
  const otherPct = Math.max(0, 100 - shown)
  const data = otherPct > 0.3 ? [...slices, { label: 'Other', value: otherPct, serious: false, color: OTHER_COLOR }] : slices

  return (
    <div className="mt-3 space-y-4 text-base">
      <p className="text-sm font-bold uppercase tracking-wide text-slate-500">
        Top {result.predictions.length} possibilit{result.predictions.length === 1 ? 'y' : 'ies'}
      </p>

      <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-center">
        {/* Donut with the headline guess in the centre */}
        <div className="relative h-44 w-44 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                nameKey="label"
                cx="50%"
                cy="50%"
                innerRadius={54}
                outerRadius={78}
                startAngle={90}
                endAngle={-270}
                paddingAngle={1.5}
                stroke="none"
                isAnimationActive={false}
              >
                {data.map((d) => (
                  <Cell key={d.label} fill={d.color} />
                ))}
              </Pie>
              <Tooltip
                formatter={(v, n) => [`${Number(v).toFixed(1)}%`, String(n)]}
                contentStyle={{ borderRadius: 12, border: '1px solid #e2e8f0', fontSize: 12 }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
            <span className="text-3xl font-extrabold tabular-nums text-slate-900">
              {(top.score * 100).toFixed(0)}%
            </span>
            <span className="mt-0.5 max-w-[5.5rem] text-sm font-bold leading-tight text-slate-600">{top.label}</span>
          </div>
        </div>

        {/* Legend */}
        <ul className="w-full space-y-2.5">
          {data.map((d) => (
            <li key={d.label} className="flex items-center gap-2.5">
              <span className="h-3.5 w-3.5 shrink-0 rounded-full" style={{ backgroundColor: d.color }} />
              <span className={`flex-1 truncate text-base ${d.label === 'Other' ? 'font-semibold text-slate-500' : 'font-bold text-slate-800'}`}>
                {d.label}
                {d.serious && (
                  <span className="ml-1.5 rounded-full bg-rose-50 px-2 py-0.5 text-xs font-bold text-rose-700">
                    see a doctor
                  </span>
                )}
              </span>
              <span className="shrink-0 text-base font-bold tabular-nums text-slate-700">{d.value.toFixed(1)}%</span>
            </li>
          ))}
        </ul>
      </div>

      <p
        className={`rounded-lg px-3 py-2.5 text-sm font-semibold ${
          result.any_serious
            ? 'bg-rose-50 text-rose-800'
            : result.low_confidence
              ? 'bg-amber-50 text-amber-800'
              : 'bg-slate-50 text-slate-600'
        }`}
      >
        {result.note}
      </p>

      <div className="flex flex-wrap gap-2 pt-1">
        <button
          onClick={() =>
            navigate('/chat', {
              state: {
                prefill:
                  `My experimental skin analysis suggested "${top.label}"` +
                  (result.predictions[1] ? ` (or possibly ${result.predictions[1].label})` : '') +
                  `. Can you explain what ${top.label} is and how to care for it? Remember this isn't a diagnosis.`,
              },
            })
          }
          className="rounded-full border border-emerald-600 px-3 py-1.5 text-sm font-medium text-emerald-700 hover:bg-emerald-50"
        >
          Ask Kashvi about this
        </button>
        {top?.concern && (
          <button
            onClick={() => navigate('/products', { state: { q: top.label } })}
            className="rounded-full border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Find products
          </button>
        )}
      </div>
    </div>
  )
}

function AcneResult({
  result,
  navigate,
}: {
  result: AcneAnalysisResult | null
  navigate: ReturnType<typeof useNavigate>
}) {
  if (!result) return <p className="mt-2 text-sm text-slate-400">No analysis yet.</p>

  if (result.model_status === 'model_not_configured') {
    return (
      <div className="mt-2 space-y-2 text-sm">
        <p className="font-medium text-slate-800">Analysis model not set up yet</p>
        <p className="text-slate-500">
          No acne-specific model is configured, so no prediction was made. Try the Skin Condition
          Check tab, which can detect acne among other conditions.
        </p>
        <p className="text-xs text-slate-400">{result.note}</p>
      </div>
    )
  }

  return (
    <div className="mt-2 space-y-2 text-sm">
      <p>
        <span className="text-slate-500">Predicted class: </span>
        <span className="font-medium text-slate-900">{result.predicted_class ?? 'n/a'}</span>
      </p>
      {result.raw_score !== null && (
        <p>
          <span className="text-slate-500">Raw model score: </span>
          <span className="font-medium text-slate-900">{result.raw_score.toFixed(3)}</span>
          <span className="ml-1 text-xs text-slate-400">(not a calibrated probability)</span>
        </p>
      )}
      <p className="text-xs text-slate-400">{result.note}</p>
      <button
        onClick={() =>
          navigate('/chat', {
            state: {
              prefill:
                `My experimental acne analysis gave predicted class "${result.predicted_class ?? 'none'}"` +
                (result.raw_score !== null ? ` with a raw model score of ${result.raw_score.toFixed(3)}` : '') +
                '. Can you explain what that means and what I can do?',
            },
          })
        }
        className="rounded-md border border-emerald-600 px-3 py-1.5 text-sm font-medium text-emerald-700 hover:bg-emerald-50"
      >
        Ask Kashvi to explain
      </button>
    </div>
  )
}
