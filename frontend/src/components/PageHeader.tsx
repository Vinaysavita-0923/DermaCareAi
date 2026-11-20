import type { ReactNode } from 'react'

/**
 * Standard page header: the serif page title and an optional muted intro
 * line. Gives every page the same masthead without changing any page's
 * logic or layout below it.
 */
export default function PageHeader({ title, intro }: { title: ReactNode; intro?: ReactNode }) {
  return (
    <div>
      <h1 className="text-3xl text-slate-900 sm:text-[2.05rem]">{title}</h1>
      {intro && <p className="mt-2 max-w-2xl text-slate-500">{intro}</p>}
    </div>
  )
}
