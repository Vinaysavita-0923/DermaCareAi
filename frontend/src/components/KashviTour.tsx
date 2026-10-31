import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export const START_TOUR_EVENT = 'kashvi:start-tour'

interface Step {
  title: string
  body: string
  route?: string
}

const STEPS: Step[] = [
  {
    title: 'Welcome to DermaCare AI!',
    body: "I'm Kashvi, your skincare companion. Let me show you around in a few quick steps.",
  },
  {
    title: 'Your Dashboard',
    body: 'Your skin profile, routine progress, journal patterns and a daily tip — all in one place.',
    route: '/dashboard',
  },
  {
    title: 'Start here: Skin Assessment',
    body: 'Answer 5 quick questions about your skin. I use them to personalise ingredient guidance and product picks.',
    route: '/skin-assessment',
  },
  {
    title: 'Skin Analysis',
    body: 'Upload a photo for an experimental, research-only acne check. Photos are never saved.',
    route: '/acne-analysis',
  },
  {
    title: 'Chat with me',
    body: 'Ask me anything about skincare — type, tap a suggested question, or use the microphone.',
    route: '/chat',
  },
  {
    title: 'Products & Ingredients',
    body: 'Browse 1,600+ products by category, search by ingredient, and open any product for its full details.',
    route: '/products',
  },
  {
    title: 'Skincare Routine',
    body: 'Build morning and night routines and mark them done each day to track your consistency.',
    route: '/routines',
  },
  {
    title: 'Skin Journal',
    body: "Log how your skin feels each day — I'll chart the patterns on your dashboard.",
    route: '/journal',
  },
  {
    title: 'Reports',
    body: 'See a 30-day summary of your journal entries and routine progress.',
    route: '/reports',
  },
  {
    title: "You're all set!",
    body: 'The best first step is your Skin Assessment — it takes about a minute.',
  },
]

function doneKey(userId: number) {
  return `kashvi.tourDone.${userId}`
}

function hasSeenTour(userId: number): boolean {
  try {
    return localStorage.getItem(doneKey(userId)) === '1'
  } catch {
    return true // storage blocked: don't nag on every page load
  }
}

function markSeen(userId: number) {
  try {
    localStorage.setItem(doneKey(userId), '1')
  } catch {
    /* storage unavailable */
  }
}

export default function KashviTour() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [step, setStep] = useState<number | null>(null)

  useEffect(() => {
    if (user && !hasSeenTour(user.id)) setStep(0)
  }, [user])

  useEffect(() => {
    const start = () => setStep(0)
    window.addEventListener(START_TOUR_EVENT, start)
    return () => window.removeEventListener(START_TOUR_EVENT, start)
  }, [])

  const current = step === null ? null : STEPS[step]

  // Open the page for this step and highlight its sidebar link.
  useEffect(() => {
    if (!current?.route) return
    navigate(current.route)
    const link = document.querySelector(`[data-tour="${current.route}"]`)
    link?.classList.add('tour-highlight')
    return () => link?.classList.remove('tour-highlight')
  }, [current, navigate])

  if (!user || step === null || !current) return null

  const last = step === STEPS.length - 1
  const firstName = user.full_name?.trim().split(/\s+/)[0]

  function finish(route?: string) {
    markSeen(user!.id)
    setStep(null)
    if (route) navigate(route)
  }

  return (
    <div
      role="dialog"
      aria-label="DermaCare AI tour"
      className="fixed inset-x-3 bottom-3 z-50 sm:inset-x-auto sm:bottom-6 sm:right-6 sm:w-[23rem]"
    >
      <div key={step} className="anim-fade-up overflow-hidden rounded-2xl border border-emerald-200 bg-white shadow-2xl" style={{ animationDuration: '0.35s' }}>
        <div className="flex items-start gap-3 bg-gradient-to-br from-emerald-50 to-white p-4">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-base font-bold text-white">
            K
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700">
              Kashvi · step {step + 1} of {STEPS.length}
            </p>
            <h2 className="mt-0.5 text-base font-semibold text-slate-900">
              {step === 0 && firstName ? `Hi ${firstName}! ` : ''}
              {current.title}
            </h2>
            <p className="mt-1 text-sm leading-relaxed text-slate-600">{current.body}</p>
          </div>
          <button
            type="button"
            onClick={() => finish()}
            aria-label="Close tour"
            className="shrink-0 rounded-full p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            ✕
          </button>
        </div>

        <div className="flex gap-1 px-4" aria-hidden="true">
          {STEPS.map((_, i) => (
            <span key={i} className={`h-1 flex-1 rounded-full ${i <= step ? 'bg-emerald-600' : 'bg-slate-200'}`} />
          ))}
        </div>

        <div className="flex items-center justify-between gap-2 p-4">
          {last ? (
            <>
              <button type="button" onClick={() => finish('/dashboard')} className="text-sm font-medium text-slate-500 hover:text-slate-800">
                Explore on my own
              </button>
              <button
                type="button"
                onClick={() => finish('/skin-assessment')}
                className="rounded-full bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
              >
                Start my assessment →
              </button>
            </>
          ) : (
            <>
              <button type="button" onClick={() => finish()} className="text-sm font-medium text-slate-400 hover:text-slate-700">
                Skip tour
              </button>
              <div className="flex gap-2">
                {step > 0 && (
                  <button
                    type="button"
                    onClick={() => setStep(step - 1)}
                    className="rounded-full border border-slate-200 px-3.5 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
                  >
                    Back
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setStep(step + 1)}
                  className="rounded-full bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
                >
                  {step === 0 ? "Let's go" : 'Next'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
