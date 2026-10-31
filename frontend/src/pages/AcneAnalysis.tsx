import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { analyzeAcneImage, type AcneAnalysisResult } from '../services/acne'
import { extractErrorMessage } from '../services/auth'

const MAX_MB = 8 // matches the backend's acne_max_image_mb default
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp']

export default function AcneAnalysis() {
  const navigate = useNavigate()
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [result, setResult] = useState<AcneAnalysisResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Release the object URL when the preview changes or the page unmounts.
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    }
  }, [previewUrl])

  function handleSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = e.target.files?.[0] ?? null
    setResult(null)
    setError(null)
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
    setError(null)
    setResult(null)
    try {
      setResult(await analyzeAcneImage(file))
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  const notConfigured = result?.model_status === 'model_not_configured'

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Acne Analysis (Experimental)</h1>
        <p className="mt-1 text-sm text-slate-500">
          Upload a clear photo of your skin. Images are analysed in memory and never stored.
        </p>
      </div>

      <div className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
        This is an experimental tool, not a diagnosis. For persistent or painful acne, please see
        a dermatologist.
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
            <img
              src={previewUrl}
              alt="Selected upload preview"
              className="max-h-72 w-full rounded-md object-contain"
            />
          )}
          <button
            onClick={handleAnalyze}
            disabled={!file || loading}
            className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {loading ? 'Analysing...' : 'Analyse image'}
          </button>
          {error && (
            <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
              {error}
            </p>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-sm font-medium text-slate-700">Result</h2>
          {!result ? (
            <p className="mt-2 text-sm text-slate-400">No analysis yet.</p>
          ) : notConfigured ? (
            <div className="mt-2 space-y-2 text-sm">
              <p className="font-medium text-slate-800">Analysis model not set up yet</p>
              <p className="text-slate-500">
                The backend has no trained model configured, so no prediction was made. Nothing
                has been guessed.
              </p>
              <p className="text-xs text-slate-400">{result.note}</p>
            </div>
          ) : (
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
                Ask the assistant to explain
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
