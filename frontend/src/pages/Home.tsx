import { Link } from 'react-router-dom'
import Credits from '../components/Credits'

const FEATURES = [
  {
    title: 'AI Skin Care Chat',
    body: 'Ask general, educational skin-care questions and get clear, non-diagnostic answers.',
  },
  {
    title: 'Experimental Acne Analysis',
    body: 'Upload a photo for a research-only, clearly labeled analysis — never a diagnosis.',
  },
  {
    title: 'Skin Journal & Routines',
    body: 'Track how your skin feels day to day and whether you kept up your routine.',
  },
  {
    title: 'Product & Ingredient Guide',
    body: 'Look up ingredients and compare products, with sample data clearly marked as such.',
  },
]

export default function Home() {
  return (
    <div className="space-y-12">
      <section className="rounded-2xl bg-gradient-to-b from-emerald-50 to-slate-50 px-4 py-10 text-center sm:py-14">
        <div className="anim-pop-in mx-auto mb-6 w-fit" style={{ '--d': '0.1s' } as React.CSSProperties}>
          <img
            src="/logo.png"
            alt="DermaCare AI - your smart skincare assistant"
            className="anim-float h-40 w-40 sm:h-52 sm:w-52"
          />
        </div>
        <h1
          className="anim-fade-up mx-auto max-w-3xl text-3xl font-bold tracking-tight text-slate-900 sm:text-5xl"
          style={{ '--d': '0.3s' } as React.CSSProperties}
        >
          A skin-care assistant that's honest about its limits
        </h1>
        <p
          className="anim-fade-up mx-auto mt-4 max-w-2xl text-lg text-slate-500"
          style={{ '--d': '0.45s' } as React.CSSProperties}
        >
          Educational information, journaling, and experimental tools to help you
          understand your skin — not a doctor, and not a diagnosis.
        </p>
        <div
          className="anim-fade-up mt-8 flex flex-wrap justify-center gap-3"
          style={{ '--d': '0.6s' } as React.CSSProperties}
        >
          <Link
            to="/login"
            className="rounded-md bg-emerald-600 px-5 py-2.5 font-medium text-white shadow-sm hover:bg-emerald-700"
          >
            Sign up / Log in
          </Link>
          <Link
            to="/dashboard"
            className="rounded-md border border-slate-300 bg-white px-5 py-2.5 font-medium text-slate-700 hover:bg-slate-50"
          >
            Explore the app
          </Link>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        {FEATURES.map((f, i) => (
          <div
            key={f.title}
            className="anim-fade-up rounded-xl border border-slate-200 bg-white p-5 transition-shadow hover:shadow-md"
            style={{ '--d': `${0.75 + i * 0.12}s` } as React.CSSProperties}
          >
            <h2 className="font-semibold text-slate-900">{f.title}</h2>
            <p className="mt-1 text-sm text-slate-500">{f.body}</p>
          </div>
        ))}
      </section>

      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        <strong>Important:</strong> This app shares general educational information only.
        It does not diagnose conditions or prescribe treatment. For severe, rapidly
        worsening, painful, or infected symptoms, please see a doctor or dermatologist.
      </section>

      <Credits />
    </div>
  )
}
