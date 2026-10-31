import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { getMyProfile, DATASET_CONCERNS, type SkinProfile } from '../services/profile'
import { getAssessmentHistory } from '../services/assessment'

const concernLabel = (tag: string) => DATASET_CONCERNS.find((c) => c.tag === tag)?.label ?? tag.replace(/_/g, ' ')

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="mb-1.5 text-sm font-medium text-slate-500">{label}</p>
      <p className="truncate rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-700">{value}</p>
    </div>
  )
}

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      <div className="mt-1 text-slate-800">{children}</div>
    </div>
  )
}

export default function Profile() {
  const { user } = useAuth()
  const [profile, setProfile] = useState<SkinProfile | null>(null)
  const [assessments, setAssessments] = useState<number | null>(null)

  useEffect(() => {
    getMyProfile().then(setProfile).catch(() => setProfile(null))
    getAssessmentHistory(100).then((h) => setAssessments(h.length)).catch(() => setAssessments(null))
  }, [])

  if (!user) return null
  const name = user.full_name?.trim() || user.email
  const joined = new Date(user.created_at).toLocaleDateString(undefined, { day: 'numeric', month: 'long', year: 'numeric' })

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <h1 className="text-3xl text-slate-900">My Profile</h1>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col items-center">
          <span className="flex h-36 w-36 items-center justify-center rounded-2xl bg-emerald-700 text-6xl font-semibold uppercase text-white ring-4 ring-emerald-100">
            {name.charAt(0)}
          </span>
        </div>
        <div className="mt-6 space-y-4">
          <Field label="Name" value={name.toUpperCase()} />
          <Field label="Email" value={user.email} />
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-xl text-slate-900">Skin details</h2>
            <p className="text-sm text-slate-500">From your latest skin assessment. Used to personalise products and Kashvi.</p>
          </div>
          <Link
            to="/skin-assessment"
            className="rounded-full border border-emerald-600 px-4 py-1.5 text-sm font-medium text-emerald-700 hover:bg-emerald-50"
          >
            {profile ? 'Update assessment' : 'Take the assessment'}
          </Link>
        </div>
        <hr className="my-4 border-slate-100" />
        {profile ? (
          <div className="grid gap-x-8 gap-y-5 rounded-xl bg-slate-50 p-5 sm:grid-cols-2 lg:grid-cols-4">
            <Detail label="Skin type">
              <span className="capitalize">
                {profile.skin_type}
                {profile.skin_subtype ? ` · ${profile.skin_subtype}` : ''}
              </span>
            </Detail>
            <Detail label="Age">{profile.age != null ? `${profile.age} yrs` : 'Not set'}</Detail>
            <Detail label="Age group">{profile.age_group ?? 'Not set'}</Detail>
            <Detail label="Sensitivity">
              {profile.is_sensitive === true ? 'Sensitive' : profile.is_sensitive === false ? 'Not sensitive' : 'Not sure'}
            </Detail>
            <div className="sm:col-span-2 lg:col-span-4">
              <Detail label="Concerns">
                {profile.concerns?.length ? (
                  <div className="mt-1.5 flex flex-wrap gap-2">
                    {profile.concerns.map((c) => (
                      <span key={c} className="rounded-full bg-rose-50 px-3 py-1 text-sm font-medium text-rose-700">
                        {concernLabel(c)}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span className="italic text-slate-400">None selected</span>
                )}
              </Detail>
            </div>
          </div>
        ) : (
          <p className="rounded-xl bg-slate-50 p-5 text-slate-500">You haven't taken a skin assessment yet.</p>
        )}
        <div className="mt-4 flex flex-wrap gap-2">
          <Link
            to="/skin-assessment"
            state={{ view: 'report' }}
            className="rounded-full bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800"
          >
            View detailed report
          </Link>
          <Link
            to="/skin-assessment"
            state={{ view: 'products' }}
            className="rounded-full border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Recommended products
          </Link>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-xl text-slate-900">Account</h2>
        <hr className="my-4 border-slate-100" />
        <div className="grid gap-5 rounded-xl bg-slate-50 p-5 sm:grid-cols-3">
          <Detail label="Member since">{joined}</Detail>
          <Detail label="Status">{user.is_active ? 'Active' : 'Inactive'}</Detail>
          <Detail label="Assessments taken">{assessments ?? '–'}</Detail>
        </div>
        <p className="mt-4 text-xs text-slate-400">Name and email can't be changed here.</p>
      </section>
    </div>
  )
}
