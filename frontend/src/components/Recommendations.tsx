import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import {
  getRecommendations,
  type IngredientStatus,
  type RecommendationResponse,
  type RecommendedProduct,
} from '../services/recommendations'
import { createRoutine, type RoutineType } from '../services/routines'
import { extractErrorMessage } from '../services/auth'

interface Props {
  /** Changes whenever the profile is saved, so the list is refetched. */
  refreshKey: number
}

const STATUS_BADGE: Record<IngredientStatus, { text: string; cls: string }> = {
  verified: { text: 'Full ingredient list verified', cls: 'bg-emerald-100 text-emerald-800' },
  partial: { text: 'Key ingredients only - check the pack', cls: 'bg-amber-100 text-amber-800' },
  unverified: { text: 'Ingredients not verified - check the pack', cls: 'bg-rose-100 text-rose-700' },
  sample: { text: 'Generic sample product', cls: 'bg-slate-100 text-slate-600' },
}

const categoryLabel = (c: string) => c.replace(/_/g, ' ')

function ProductCard({ p, onOpen }: { p: RecommendedProduct; onOpen: () => void }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="group flex w-full items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-left transition hover:-translate-y-0.5 hover:border-emerald-200 hover:shadow-md"
    >
      <span className="min-w-0">
        {p.brand && !p.is_sample_data && (
          <span className="block truncate text-xs font-medium text-slate-400">{p.brand}</span>
        )}
        <span className="block font-medium leading-snug text-slate-900">{p.name}</span>
        <span className="mt-0.5 block text-xs capitalize text-emerald-700">{categoryLabel(p.category)}</span>
      </span>
      <span className="shrink-0 text-lg text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-emerald-600" aria-hidden="true">
        ›
      </span>
    </button>
  )
}

function DetailSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{title}</h4>
      <div className="mt-1.5">{children}</div>
    </div>
  )
}

function ProductDetailModal({ p, onClose }: { p: RecommendedProduct; onClose: () => void }) {
  const badge = STATUS_BADGE[p.ingredient_status]
  const warnings = p.warnings.filter((w) => p.ingredient_status !== 'sample' || !w.startsWith('Generic sample'))

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-label={p.name}
        className="flex max-h-[88vh] w-full max-w-xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-6 py-5">
          <div>
            {p.brand && !p.is_sample_data && <p className="text-sm font-medium text-slate-500">{p.brand}</p>}
            <h3 className="text-xl font-semibold leading-snug text-slate-900">{p.name}</h3>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium capitalize text-slate-600">
                {categoryLabel(p.category)}
              </span>
              {p.usage_time && (
                <span className="rounded-full bg-sky-50 px-2.5 py-0.5 text-xs font-medium capitalize text-sky-700">
                  {p.usage_time === 'both' ? 'Morning & night' : p.usage_time}
                </span>
              )}
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${badge.cls}`}>{badge.text}</span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="shrink-0 rounded-full p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            ✕
          </button>
        </div>

        <div className="space-y-5 overflow-y-auto px-6 py-5 text-sm">
          {p.description && <p className="text-[15px] leading-relaxed text-slate-700">{p.description}</p>}

          {p.match_reasons.length > 0 && (
            <DetailSection title="Why it matches you">
              <ul className="flex flex-wrap gap-1.5">
                {p.match_reasons.map((r) => (
                  <li key={r} className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
                    {r}
                  </li>
                ))}
              </ul>
            </DetailSection>
          )}

          {p.uses && (
            <DetailSection title="Uses">
              <p className="leading-relaxed text-slate-700">{p.uses}</p>
            </DetailSection>
          )}

          {p.how_to_use && (
            <DetailSection title="How to use">
              <p className="leading-relaxed text-slate-700">{p.how_to_use}</p>
            </DetailSection>
          )}

          {p.ingredients.length > 0 && p.ingredient_status !== 'sample' && (
            <DetailSection
              title={`${p.ingredient_status === 'verified' ? 'Ingredients' : 'Key ingredients'} · ${p.ingredients.length}`}
            >
              <div className="flex flex-wrap gap-1.5">
                {p.ingredients.map((ing, i) => (
                  <span key={`${ing}-${i}`} className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-xs text-slate-700">
                    {ing}
                  </span>
                ))}
              </div>
            </DetailSection>
          )}

          {(p.cautions || warnings.length > 0) && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-amber-800">
              <p className="text-[11px] font-semibold uppercase tracking-wide">⚠ Caution</p>
              {p.cautions && <p className="mt-1 leading-relaxed">{p.cautions}</p>}
              {warnings.map((w) => (
                <p key={w} className="mt-1 leading-relaxed">
                  {w}
                </p>
              ))}
            </div>
          )}
        </div>

        {p.source_url && (
          <p className="truncate border-t border-slate-100 px-6 py-3 text-xs text-slate-400">
            Source:{' '}
            <a href={p.source_url} target="_blank" rel="noopener noreferrer" className="underline hover:text-slate-600">
              {p.source_url}
            </a>
          </p>
        )}
      </div>
    </div>
  )
}

export default function Recommendations({ refreshKey }: Props) {
  const [pregnant, setPregnant] = useState(false)
  const [data, setData] = useState<RecommendationResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [creating, setCreating] = useState<RoutineType | null>(null)
  const [open, setOpen] = useState<RecommendedProduct | null>(null)
  const closeDetail = useCallback(() => setOpen(null), [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getRecommendations(pregnant)
      .then((r) => !cancelled && setData(r))
      .catch((err) => !cancelled && setError(extractErrorMessage(err)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [pregnant, refreshKey])

  async function createFrom(type: RoutineType, products: RecommendedProduct[]) {
    setCreating(type)
    setError(null)
    setMessage(null)
    try {
      await createRoutine(
        type,
        products.map((p, i) => ({
          product_id: p.product_id,
          step_order: i + 1,
          notes: p.product_id === null ? p.name : p.how_to_use,
        })),
      )
      setMessage(`Your ${type} routine was created. You can log it on the Routines page.`)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setCreating(null)
    }
  }

  const blocks: { type: RoutineType; title: string; items: RecommendedProduct[] }[] = data
    ? [
        { type: 'morning', title: 'Morning', items: data.routine.morning },
        { type: 'night', title: 'Evening', items: data.routine.evening },
      ]
    : []
  const inRoutine = new Set(data ? [...data.routine.morning, ...data.routine.evening].map((p) => p.name) : [])
  const others = data ? data.matches.filter((p) => !inRoutine.has(p.name)) : []

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold text-slate-900">Recommended for you</h2>
        <p className="mt-1 text-sm text-slate-500">
          Products matched to your saved skin type and concerns. Tap a product to see its full details.
        </p>
      </div>

      <label className="flex items-center gap-2 text-sm text-slate-600">
        <input
          type="checkbox"
          checked={pregnant}
          onChange={(e) => setPregnant(e.target.checked)}
          className="h-4 w-4 accent-emerald-600"
        />
        I am pregnant or trying to conceive (hides products with retinoids and acids)
      </label>

      {error && (
        <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          {message} <Link to="/routines" className="font-medium underline">Open Routines</Link>
        </p>
      )}

      {loading && !data ? (
        <p className="text-sm text-slate-400">Finding matches...</p>
      ) : data ? (
        <>
          {data.notes.length > 0 && (
            <ul className="space-y-1 rounded-md bg-slate-100 px-3 py-2 text-xs text-slate-600">
              {data.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          )}

          {data.matches.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
              No products match these settings. Try removing a filter or changing your concerns.
            </div>
          ) : (
            <>
              <div className="grid gap-4 md:grid-cols-2">
                {blocks.map((b) => (
                  <div key={b.type} className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <div className="flex items-center justify-between">
                      <h3 className="font-medium text-slate-800">{b.title} routine</h3>
                      <button
                        onClick={() => createFrom(b.type, b.items)}
                        disabled={b.items.length === 0 || creating !== null}
                        className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                      >
                        {creating === b.type ? 'Creating...' : 'Create this routine'}
                      </button>
                    </div>
                    {b.items.length === 0 ? (
                      <p className="text-sm text-slate-400">No suitable steps found.</p>
                    ) : (
                      b.items.map((p, i) => (
                        <div key={p.name} className="flex gap-2">
                          <span className="pt-3 text-sm text-slate-400">{i + 1}.</span>
                          <div className="flex-1">
                            <ProductCard p={p} onOpen={() => setOpen(p)} />
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                ))}
              </div>

              {others.length > 0 && (
                <div>
                  <h3 className="mb-2 font-medium text-slate-800">Other matches</h3>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {others.map((p) => (
                      <ProductCard key={p.name} p={p} onOpen={() => setOpen(p)} />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">{data.disclaimer}</p>
        </>
      ) : null}

      {open && <ProductDetailModal p={open} onClose={closeDetail} />}
    </section>
  )
}
