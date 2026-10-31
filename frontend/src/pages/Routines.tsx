import { useEffect, useState } from 'react'
import {
  createRoutine,
  deleteRoutine,
  listRoutines,
  logRoutineDay,
  type Routine,
  type RoutineType,
} from '../services/routines'
import { searchProducts, type Product } from '../services/products'
import { extractErrorMessage } from '../services/auth'

interface DraftStep {
  product_id: number | null
  notes: string
}

function todayISO(): string {
  const d = new Date()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${month}-${day}`
}

export default function Routines() {
  const [routines, setRoutines] = useState<Routine[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const [type, setType] = useState<RoutineType>('morning')
  const [steps, setSteps] = useState<DraftStep[]>([{ product_id: null, notes: '' }])
  const [saving, setSaving] = useState(false)

  function reload() {
    return listRoutines()
      .then(setRoutines)
      .catch((err) => setError(extractErrorMessage(err)))
  }

  useEffect(() => {
    Promise.all([reload(), searchProducts().then(setProducts).catch(() => setProducts([]))]).finally(
      () => setLoading(false),
    )
  }, [])

  function updateStep(i: number, patch: Partial<DraftStep>) {
    setSteps((prev) => prev.map((s, idx) => (idx === i ? { ...s, ...patch } : s)))
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      const items = steps
        .filter((s) => s.product_id !== null || s.notes.trim() !== '')
        .map((s, i) => ({
          product_id: s.product_id,
          step_order: i + 1,
          notes: s.notes.trim() || null,
        }))
      await createRoutine(type, items)
      setSteps([{ product_id: null, notes: '' }])
      setMessage('Routine created.')
      await reload()
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  async function handleLog(id: number, completed: boolean) {
    setError(null)
    setMessage(null)
    try {
      await logRoutineDay(id, todayISO(), completed)
      setMessage(completed ? 'Logged as completed today.' : 'Logged as skipped today.')
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  async function handleDelete(id: number) {
    if (!window.confirm('Delete this routine and its logs?')) return
    setError(null)
    setMessage(null)
    try {
      await deleteRoutine(id)
      await reload()
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  const productName = (id: number | null) =>
    id === null ? null : (products.find((p) => p.id === id)?.name ?? `Product #${id}`)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Routines</h1>
        <p className="mt-1 text-sm text-slate-500">
          Build a morning or night routine and log each day. Logs feed the Reports page.
        </p>
      </div>

      {error && (
        <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
          {error}
        </p>
      )}
      {message && <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{message}</p>}

      <form onSubmit={handleCreate} className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-sm font-medium text-slate-700">New routine</h2>
        <select
          value={type}
          onChange={(e) => setType(e.target.value as RoutineType)}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="morning">Morning</option>
          <option value="night">Night</option>
        </select>

        {steps.map((s, i) => (
          <div key={i} className="flex flex-wrap gap-2">
            <span className="w-6 pt-2 text-sm text-slate-400">{i + 1}.</span>
            <select
              value={s.product_id ?? ''}
              onChange={(e) =>
                updateStep(i, { product_id: e.target.value ? Number(e.target.value) : null })
              }
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">No product</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <input
              type="text"
              value={s.notes}
              onChange={(e) => updateStep(i, { notes: e.target.value })}
              placeholder="Notes (e.g. cleanse, 60 seconds)"
              className="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none"
            />
            {steps.length > 1 && (
              <button
                type="button"
                onClick={() => setSteps((prev) => prev.filter((_, idx) => idx !== i))}
                className="text-sm text-slate-400 hover:text-rose-600"
              >
                Remove
              </button>
            )}
          </div>
        ))}

        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setSteps((prev) => [...prev, { product_id: null, notes: '' }])}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"
          >
            Add step
          </button>
          <button
            type="submit"
            disabled={saving}
            className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Create routine'}
          </button>
        </div>
      </form>

      {loading ? (
        <p className="py-8 text-center text-slate-400">Loading routines...</p>
      ) : routines.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-slate-500">
          No routines yet. Create your first one above.
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {routines.map((r) => (
            <div key={r.id} className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-start justify-between">
                <p className="font-medium capitalize text-slate-900">{r.routine_type} routine</p>
                <button
                  onClick={() => handleDelete(r.id)}
                  className="text-sm text-slate-400 hover:text-rose-600"
                >
                  Delete
                </button>
              </div>
              {r.items.length === 0 ? (
                <p className="mt-2 text-sm text-slate-400">No steps.</p>
              ) : (
                <ol className="mt-2 space-y-1 text-sm text-slate-600">
                  {[...r.items]
                    .sort((a, b) => a.step_order - b.step_order)
                    .map((it) => (
                      <li key={it.id}>
                        {it.step_order}. {productName(it.product_id) ?? 'Step'}
                        {it.notes && <span className="text-slate-400"> - {it.notes}</span>}
                      </li>
                    ))}
                </ol>
              )}
              <div className="mt-3 flex gap-2">
                <button
                  onClick={() => handleLog(r.id, true)}
                  className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700"
                >
                  Done today
                </button>
                <button
                  onClick={() => handleLog(r.id, false)}
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
                >
                  Skipped today
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
