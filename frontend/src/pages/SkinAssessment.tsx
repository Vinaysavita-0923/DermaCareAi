import { useEffect, useState, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  DATASET_CONCERNS,
  SKIN_TYPES,
  SUBTYPES_BY_SKIN_TYPE,
  type SkinType,
} from '../services/profile'
import {
  getMyAssessment,
  getAssessmentRecommendations,
  getPersonalizedProfile,
  submitAssessment,
  type AssessmentCreateResponse,
  type PersonalizedProfile,
  type AssessmentRecommendations,
  type IngredientGuidance,
} from '../services/assessment'
import { useAuth } from '../hooks/useAuth'
import { extractErrorMessage } from '../services/auth'
import Recommendations from '../components/Recommendations'

type Sensitivity = 'yes' | 'no' | 'not_sure'
type ResultView = 'summary' | 'profile' | 'recommendations'

const STEP_TITLES = ['Personal Information', 'Skin Type', 'Skin Sensitivity', 'Skin Concerns', 'Review']

export default function SkinAssessment() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  // The dashboard links here with { view: 'report' | 'products' } to open
  // the saved assessment's report or product list straight away.
  const openView = (location.state as { view?: 'report' | 'products' } | null)?.view
  const [fromSaved, setFromSaved] = useState(false)

  const [loading, setLoading] = useState(true)
  const [step, setStep] = useState(1)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  // Form state
  const [fullName, setFullName] = useState('')
  const [age, setAge] = useState('')
  const [skinType, setSkinType] = useState<SkinType>('unsure')
  const [skinSubtype, setSkinSubtype] = useState<string | null>(null)
  const [sensitivity, setSensitivity] = useState<Sensitivity | null>(null)
  const [notes, setNotes] = useState('')
  const [concerns, setConcerns] = useState<string[]>([])

  // Post-submit result state
  const [result, setResult] = useState<AssessmentCreateResponse | null>(null)
  const [resultView, setResultView] = useState<ResultView>('summary')
  const [personalizedProfile, setPersonalizedProfile] = useState<PersonalizedProfile | null>(null)
  const [recommendations, setRecommendations] = useState<AssessmentRecommendations | null>(null)
  const [loadingResult, setLoadingResult] = useState(false)

  useEffect(() => {
    getMyAssessment()
      .then((profile) => {
        if (profile) {
          setAge(profile.age != null ? String(profile.age) : '')
          setSkinType(profile.skin_type)
          setSkinSubtype(profile.skin_subtype)
          setSensitivity(profile.is_sensitive === true ? 'yes' : profile.is_sensitive === false ? 'no' : 'not_sure')
          setNotes(profile.sensitivity_notes ?? '')
          setConcerns(profile.concerns ?? [])
          if (openView) {
            setResult({ ...profile, history_id: 0, age_group_note: null })
            setFromSaved(true)
            if (openView === 'report') openProfile()
            else openRecommendations()
          }
        }
        setFullName(user?.full_name ?? '')
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function toggleConcern(tag: string) {
    setConcerns((prev) => (prev.includes(tag) ? prev.filter((c) => c !== tag) : [...prev, tag]))
  }

  function selectSkinType(t: SkinType) {
    setSkinType(t)
    setSkinSubtype(null) // subtypes differ per type — never carry a stale one across
  }

  const ageNum = Number(age)
  const ageValid = age.trim() !== '' && Number.isInteger(ageNum) && ageNum >= 1 && ageNum <= 120

  function canAdvance(current: number): boolean {
    if (current === 1) return ageValid
    if (current === 3) return sensitivity !== null
    return true
  }

  async function handleSubmit() {
    setError(null)
    setSaving(true)
    try {
      const res = await submitAssessment({
        full_name: fullName.trim() || undefined,
        age: ageNum,
        skin_type: skinType,
        skin_subtype: skinType === 'unsure' ? undefined : skinSubtype ?? undefined,
        is_sensitive: sensitivity === 'yes' ? true : sensitivity === 'no' ? false : null,
        sensitivity_notes: notes.trim() || undefined,
        concerns,
      })
      setResult(res)
      setFromSaved(false)
      setPersonalizedProfile(null)
      setRecommendations(null)
      setResultView('summary')
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  async function openProfile() {
    setResultView('profile')
    if (personalizedProfile) return
    setLoadingResult(true)
    try {
      setPersonalizedProfile(await getPersonalizedProfile())
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoadingResult(false)
    }
  }

  async function openRecommendations() {
    setResultView('recommendations')
    if (recommendations) return
    setLoadingResult(true)
    try {
      setRecommendations(await getAssessmentRecommendations())
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoadingResult(false)
    }
  }

  if (loading) {
    return <p className="py-12 text-center text-slate-400">Loading your assessment…</p>
  }

  if (result) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-6 text-center">
          <h1 className="text-2xl font-semibold text-emerald-900">
            {fromSaved ? 'Your Skin Assessment Report' : 'Your Skin Profile Has Been Created!'}
          </h1>
          <p className="mx-auto mt-2 max-w-xl text-sm text-emerald-800">
            {skinType} skin
            {result.skin_subtype ? ` (${result.skin_subtype})` : ''}, age group {result.age_group}
            {result.age_group_note ? ` — ${result.age_group_note}` : ''}.
          </p>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            <button
              onClick={openProfile}
              className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
            >
              View Skin Profile
            </button>
            <button
              onClick={openRecommendations}
              className="rounded-md border border-emerald-600 px-4 py-2 text-sm font-medium text-emerald-700 hover:bg-emerald-100"
            >
              Explore Recommended Products
            </button>
            <button
              onClick={openRecommendations}
              className="rounded-md border border-emerald-600 px-4 py-2 text-sm font-medium text-emerald-700 hover:bg-emerald-100"
            >
              Generate Skincare Routine
            </button>
            <button
              onClick={() => navigate('/chat')}
              className="rounded-md border border-emerald-600 px-4 py-2 text-sm font-medium text-emerald-700 hover:bg-emerald-100"
            >
              Chat with Kashvi
            </button>
          </div>
          <button
            onClick={() => setResult(null)}
            className="mt-3 text-xs font-medium text-emerald-700 underline"
          >
            {fromSaved ? 'Retake / edit my assessment' : 'Edit my answers'}
          </button>
        </div>

        {error && (
          <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
            {error}
          </p>
        )}

        {resultView === 'recommendations' && loadingResult && (
          <p className="py-6 text-center text-sm text-slate-400">Loading…</p>
        )}

        {resultView === 'profile' && (loadingResult || personalizedProfile) && (
          <ProfileModal
            profile={personalizedProfile}
            loading={loadingResult}
            onClose={() => setResultView('summary')}
            fullName={fullName || user?.full_name || '—'}
            age={age || '—'}
            skinTypeLabel={SKIN_TYPES.find((t) => t.value === skinType)?.label ?? skinType}
            skinSubtype={skinSubtype}
            sensitivityLabel={sensitivity === 'yes' ? 'Yes' : sensitivity === 'no' ? 'No' : 'Not sure'}
          />
        )}

        {resultView === 'recommendations' && recommendations && !loadingResult && <Recommendations refreshKey={0} />}
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Skin Assessment</h1>
        <p className="mt-1 text-sm text-slate-500">
          A few questions used to personalize educational content across the app — not a diagnosis.
        </p>
      </div>

      <ol className="flex flex-wrap gap-2 text-xs">
        {STEP_TITLES.map((title, i) => (
          <li
            key={title}
            className={`rounded-full px-3 py-1 font-medium ${
              step === i + 1
                ? 'bg-emerald-600 text-white'
                : step > i + 1
                  ? 'bg-emerald-50 text-emerald-700'
                  : 'bg-slate-100 text-slate-400'
            }`}
          >
            {i + 1}. {title}
          </li>
        ))}
      </ol>

      <div className="space-y-6 rounded-xl border border-slate-200 bg-white p-6">
        {step === 1 && (
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Full name</label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                maxLength={255}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Age</label>
              <input
                type="number"
                min={1}
                max={120}
                value={age}
                onChange={(e) => setAge(e.target.value)}
                placeholder="e.g. 24"
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none"
              />
              {age.trim() !== '' && !ageValid && (
                <p className="mt-1 text-xs text-rose-600">Enter a whole number between 1 and 120.</p>
              )}
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Skin type</label>
              <div className="flex flex-wrap gap-2">
                {SKIN_TYPES.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => selectSkinType(opt.value)}
                    className={`rounded-full border px-3 py-1.5 text-sm font-medium transition-colors ${
                      skinType === opt.value
                        ? 'border-emerald-600 bg-emerald-600 text-white'
                        : 'border-slate-300 text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {skinType !== 'unsure' && (
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">
                  Skin subtype <span className="font-normal text-slate-400">(optional)</span>
                </label>
                <div className="flex flex-wrap gap-2">
                  {SUBTYPES_BY_SKIN_TYPE[skinType].map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setSkinSubtype(skinSubtype === s ? null : s)}
                      className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
                        skinSubtype === s
                          ? 'border-emerald-600 bg-emerald-50 text-emerald-700'
                          : 'border-slate-300 text-slate-600 hover:bg-slate-50'
                      }`}
                    >
                      {s}
                    </button>
                  ))}
                </div>
                {!skinSubtype && (
                  <p className="mt-1 text-xs text-slate-400">
                    Not sure? Leave this blank — we'll show guidance for both subtypes.
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">
                Does your skin experience irritation, redness, burning, itching or reactions when using
                skincare products?
              </label>
              <div className="flex flex-wrap gap-2">
                {(['yes', 'no', 'not_sure'] as Sensitivity[]).map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => setSensitivity(opt)}
                    className={`rounded-full border px-3 py-1.5 text-sm font-medium capitalize transition-colors ${
                      sensitivity === opt
                        ? 'border-emerald-600 bg-emerald-600 text-white'
                        : 'border-slate-300 text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    {opt === 'not_sure' ? "I'm not sure" : opt}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Sensitivity notes <span className="font-normal text-slate-400">(optional)</span>
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                maxLength={1000}
                placeholder="Describe any ingredients, products or environmental factors that cause irritation."
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none"
              />
            </div>
          </div>
        )}

        {step === 4 && (
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">
              Main skin concerns <span className="font-normal text-slate-400">(select any that apply)</span>
            </label>
            <div className="flex flex-wrap gap-2">
              {DATASET_CONCERNS.map(({ tag, label }) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => toggleConcern(tag)}
                  className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
                    concerns.includes(tag)
                      ? 'border-emerald-600 bg-emerald-50 text-emerald-700'
                      : 'border-slate-300 text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        )}

        {step === 5 && (
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-slate-700">Review your answers</h3>
            <dl className="space-y-2 text-sm">
              <ReviewRow label="Name" value={fullName || '—'} />
              <ReviewRow label="Age" value={age || '—'} />
              <ReviewRow
                label="Skin type"
                value={SKIN_TYPES.find((t) => t.value === skinType)?.label ?? skinType}
              />
              <ReviewRow label="Skin subtype" value={skinSubtype ?? 'Not specified'} />
              <ReviewRow
                label="Sensitivity"
                value={sensitivity === 'yes' ? 'Yes' : sensitivity === 'no' ? 'No' : "Not sure"}
              />
              <ReviewRow
                label="Concerns"
                value={
                  concerns.length > 0
                    ? concerns
                        .map((c) => DATASET_CONCERNS.find((d) => d.tag === c)?.label ?? c)
                        .join(', ')
                    : 'None selected'
                }
              />
              {notes && <ReviewRow label="Notes" value={notes} />}
            </dl>
          </div>
        )}

        {error && (
          <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
            {error}
          </p>
        )}

        <div className="flex justify-between gap-3 pt-2">
          <button
            type="button"
            onClick={() => (step === 1 ? navigate('/dashboard') : setStep(step - 1))}
            className="rounded-md border border-slate-300 px-5 py-2.5 font-medium text-slate-600 hover:bg-slate-50"
          >
            {step === 1 ? 'Cancel' : 'Back'}
          </button>
          {step < 5 ? (
            <button
              type="button"
              disabled={!canAdvance(step)}
              onClick={() => setStep(step + 1)}
              className="rounded-md bg-emerald-600 px-5 py-2.5 font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              Next
            </button>
          ) : (
            <button
              type="button"
              disabled={saving}
              onClick={handleSubmit}
              className="rounded-md bg-emerald-600 px-5 py-2.5 font-medium text-white hover:bg-emerald-700 disabled:opacity-60"
            >
              {saving ? 'Saving…' : 'Submit Assessment'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function ReviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 border-b border-slate-100 pb-2">
      <dt className="shrink-0 text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800">{value}</dd>
    </div>
  )
}

function ProfileModal({
  profile,
  loading,
  onClose,
  fullName,
  age,
  skinTypeLabel,
  skinSubtype,
  sensitivityLabel,
}: {
  profile: PersonalizedProfile | null
  loading: boolean
  onClose: () => void
  fullName: string
  age: string
  skinTypeLabel: string
  skinSubtype: string | null
  sensitivityLabel: string
}) {
  const sensitivityText =
    sensitivityLabel === 'Yes' ? 'Sensitive' : sensitivityLabel === 'No' ? 'Not sensitive' : 'Sensitivity not specified'
  const concerns = profile?.concerns_with_guidance ?? []
  const cardCount = concerns.reduce((n, cg) => n + Object.values(cg.variants).reduce((m, rows) => m + rows.length, 0), 0)
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4" onClick={onClose}>
      <div
        className="no-glow flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-slate-200 px-6 py-4">
          <div className="min-w-0">
            <h2 className="text-xl text-slate-900">Your Skin Profile</h2>
            <div className="mt-2 flex flex-wrap gap-2 text-xs font-medium">
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-700">{fullName}</span>
              <span className="rounded-full bg-violet-50 px-2.5 py-1 text-violet-700">{age} yrs</span>
              <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                {skinTypeLabel}
                {skinSubtype ? ` (${skinSubtype})` : ''}
              </span>
              <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">{sensitivityText}</span>
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

        <div className="overflow-y-auto bg-slate-50/60 px-6 py-5">
          {loading || !profile ? (
            <p className="py-10 text-center text-sm text-slate-400">Loading…</p>
          ) : (
            <div className="space-y-5">
              <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
                <p className="text-sm text-slate-700">{profile.skin_profile_summary}.</p>
                {profile.notes.map((n) => (
                  <p key={n} className="mt-2 rounded-lg bg-sky-50 px-3 py-2 text-xs text-slate-600">
                    {n}
                  </p>
                ))}
              </div>

              {concerns.length === 0 ? (
                <p className="text-sm text-slate-500">No ingredient guidance is available for your saved concerns yet.</p>
              ) : (
                <>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                    {concerns.length} concern{concerns.length === 1 ? '' : 's'} · {cardCount} guidance card
                    {cardCount === 1 ? '' : 's'}
                  </p>
                  {concerns.map((cg) => (
                    <div key={cg.concern} className="grid items-start gap-4 md:grid-cols-2">
                      {Object.entries(cg.variants).map(([key, rows]) => {
                        const [variantSensitivity, subtype] = key.split('|')
                        const showVariantLabel = Object.keys(cg.variants).length > 1
                        return rows.map((r, i) => (
                          <div key={`${key}-${i}`} className="rounded-xl border border-slate-200 bg-white p-5">
                            {showVariantLabel && (
                              <p className="mb-3 inline-block rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                                {subtype} · {variantSensitivity === 'Yes' ? 'if sensitive' : 'if not sensitive'}
                              </p>
                            )}
                            <div className="mb-4 grid grid-cols-2 gap-4 border-b border-slate-100 pb-4">
                              <GuidanceSection step={1} label="Concern" last>
                                <p className="text-base font-semibold text-slate-900">{cg.concern}</p>
                              </GuidanceSection>
                              <GuidanceSection step={2} label="Internal Type" last>
                                <p className="font-medium text-slate-800">{r.internal_type}</p>
                              </GuidanceSection>
                            </div>
                            <GuidanceSection step={3} label="Ingredients, Concentrations & Effects">
                              <IngredientsConcentrationsEffects row={r} />
                            </GuidanceSection>
                            <GuidanceSection step={4} label="Treatment Profile" last>
                              <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm leading-relaxed text-emerald-900">
                                {r.treatment_profile}
                              </p>
                            </GuidanceSection>
                          </div>
                        ))
                      })}
                    </div>
                  ))}
                </>
              )}

              {profile.concerns_without_guidance.length > 0 && (
                <p className="text-xs text-slate-400">
                  No ingredient-formulation data available for: {profile.concerns_without_guidance.join(', ')}.
                </p>
              )}

              <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">{profile.disclaimer}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function GuidanceSection({
  step,
  label,
  last,
  children,
}: {
  step: number
  label: string
  last?: boolean
  children: ReactNode
}) {
  return (
    <div className={last ? '' : 'mb-4 border-b border-slate-100 pb-4'}>
      <div className="mb-1.5 flex items-center gap-2">
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-[10px] font-semibold text-white">
          {step}
        </span>
        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      </div>
      <div className="pl-7">{children}</div>
    </div>
  )
}

function IngredientsConcentrationsEffects({ row }: { row: IngredientGuidance }) {
  const names = row.ingredients.split('+').map((s) => s.trim()).filter(Boolean)
  const amounts = row.concentrations.split('+').map((s) => s.trim())
  return (
    <div className="space-y-2.5">
      <div className="flex flex-wrap gap-1.5">
        {names.map((name, j) => (
          <span
            key={`${name}-${j}`}
            className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-700"
          >
            {name}
            {amounts[j] ? ` ${amounts[j]}` : ''}
          </span>
        ))}
      </div>
      <ul className="space-y-0.5 text-sm text-slate-600">
        {row.effects.map((effect, j) => (
          <li key={j} className="flex gap-1.5">
            <span className="text-emerald-500">•</span>
            {effect}
          </li>
        ))}
      </ul>
    </div>
  )
}
