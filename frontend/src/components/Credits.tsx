import type { ReactNode } from 'react'

const DEVELOPERS = [
  {
    name: 'Vinay Savita',
    photo: '/team/vinay-savita.jpg',
    detail: 'Electronics & Telecom, 2024–2028',
    linkedin: 'https://www.linkedin.com/in/vinay-savita0923/',
    email: 'vinaysavita0923@gmail.com',
  },
  {
    name: 'Vansh Kirar',
    photo: '/team/vansh-kirar.jpg',
    detail: 'Electronics & Telecom, 2024–2028',
    linkedin: 'https://www.linkedin.com/in/vansh-kirar-675809349/',
    email: 'vanshkirar2005@gmail.com',
  },
]

const MENTOR = {
  name: 'Dr. Himanshu Singh',
  photo: '/team/himanshu-singh.jpg',
  title: 'Assistant Professor, MITS',
}

function IconLink({ href, label, children }: { href: string; label: string; children: ReactNode }) {
  const external = href.startsWith('http')
  return (
    <a
      href={href}
      aria-label={label}
      title={label}
      {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
      className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-700"
    >
      {children}
    </a>
  )
}

const LINKEDIN_PATH =
  'M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5ZM3 9.5h4V21H3V9.5Zm6.5 0h3.8v1.6h.05c.53-1 1.84-2.05 3.78-2.05 4.04 0 4.79 2.66 4.79 6.12V21h-4v-5.1c0-1.22-.02-2.78-1.7-2.78-1.7 0-1.96 1.33-1.96 2.7V21h-4V9.5Z'

export default function Credits() {
  return (
    <section aria-labelledby="credits-heading" className="mx-auto mt-16 max-w-3xl border-t border-slate-200 pt-10 text-center">
      <p id="credits-heading" className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">
        Developed by
      </p>
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        {DEVELOPERS.map((d) => (
          <div
            key={d.name}
            className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
          >
            <img
              src={d.photo}
              alt={d.name}
              loading="lazy"
              className="h-20 w-20 shrink-0 rounded-full object-cover ring-2 ring-emerald-500 ring-offset-2"
            />
            <div className="min-w-0">
              <p className="truncate text-base font-semibold text-slate-900">{d.name}</p>
              <p className="text-xs font-medium text-emerald-700">{d.detail}</p>
              <div className="mt-2.5 flex gap-2">
                <IconLink href={d.linkedin} label={`${d.name} on LinkedIn`}>
                  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden="true">
                    <path d={LINKEDIN_PATH} />
                  </svg>
                </IconLink>
                <IconLink href={`mailto:${d.email}`} label={`Email ${d.name}`}>
                  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <rect x="3" y="5" width="18" height="14" rx="2" />
                    <path d="m3 7 9 6 9-6" />
                  </svg>
                </IconLink>
              </div>
            </div>
          </div>
        ))}
      </div>

      <p className="mt-10 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Built under the guidance of</p>
      <div className="mt-4 flex flex-col items-center">
        <span className="block h-20 w-20 overflow-hidden rounded-full ring-2 ring-emerald-500 ring-offset-2">
          {/* the source photo is a circle on black; zoom slightly to hide the corners */}
          <img src={MENTOR.photo} alt={MENTOR.name} loading="lazy" className="h-full w-full scale-110 object-cover" />
        </span>
        <p className="mt-3 text-base font-semibold text-slate-900">{MENTOR.name}</p>
        <p className="text-xs text-slate-500">{MENTOR.title}</p>
      </div>
    </section>
  )
}
