import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getReportSummary, type ReportSummary } from '../services/reports'
import { extractErrorMessage } from '../services/auth'

const PERIODS = [7, 30, 90]

export default function Reports() {
  const [days, setDays] = useState(30)
  const [report, setReport] = useState<ReportSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getReportSummary(days)
      .then((r) => !cancelled && setReport(r))
      .catch((err) => !cancelled && setError(extractErrorMessage(err)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [days])

  const tagData = report
    ? Object.entries(report.feeling_tag_counts)
        .map(([tag, count]) => ({ tag, count }))
        .sort((a, b) => b.count - a.count)
    : []

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Reports</h1>
          <p className="mt-1 text-sm text-slate-500">A summary of what you have logged.</p>
        </div>
        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <button
              key={p}
              onClick={() => setDays(p)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                days === p
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'border border-slate-300 text-slate-600 hover:bg-slate-100'
              }`}
            >
              {p} days
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
          {error}
        </p>
      )}

      {loading && !report ? (
        <p className="py-8 text-center text-slate-400">Loading report...</p>
      ) : report ? (
        <>
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <p className="text-sm text-slate-500">Journal entries in the last {report.period_days} days</p>
            <p className="mt-1 text-3xl font-semibold text-slate-900">{report.journal_entry_count}</p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-medium text-slate-700">Skin-feeling tags you logged</h2>
            {tagData.length === 0 ? (
              <p className="mt-2 text-sm text-slate-400">No tags logged in this period.</p>
            ) : (
              <div className="mt-3 h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={tagData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="tag" />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#5a9150" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-medium text-slate-700">Routine completion</h2>
            {report.routine_completion.length === 0 ? (
              <p className="mt-2 text-sm text-slate-400">
                No routines yet. Create one on the Routines page to start tracking.
              </p>
            ) : (
              <ul className="mt-3 space-y-3">
                {report.routine_completion.map((r) => {
                  const pct = Math.round(r.completion_rate * 100)
                  return (
                    <li key={r.routine_id}>
                      <div className="flex justify-between text-sm">
                        <span className="font-medium capitalize text-slate-800">
                          {r.routine_type} routine
                        </span>
                        <span className="text-slate-500">
                          {r.days_completed} of {r.days_logged} logged days completed ({pct}%)
                        </span>
                      </div>
                      <div className="mt-1 h-2 rounded-full bg-slate-100">
                        <div className="h-2 rounded-full bg-emerald-500" style={{ width: `${pct}%` }} />
                      </div>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>

          <p className="rounded-md bg-slate-100 px-3 py-2 text-xs text-slate-500">{report.disclaimer}</p>
        </>
      ) : null}
    </div>
  )
}
