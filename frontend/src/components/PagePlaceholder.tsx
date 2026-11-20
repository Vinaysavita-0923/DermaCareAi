interface Props {
  title: string
  description: string
  plannedPhase: string
}

/** Every page below is a real route today, with real content coming in
 * a later, explicitly scoped phase — not a silently empty page. */
export default function PagePlaceholder({ title, description, plannedPhase }: Props) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center">
      <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
      <p className="mx-auto mt-2 max-w-md text-slate-500">{description}</p>
      <p className="mt-4 inline-block rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-500">
        Coming in: {plannedPhase}
      </p>
    </div>
  )
}
