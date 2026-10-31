import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import {
  countProducts,
  getProduct,
  getProductCategories,
  searchProducts,
  type Product,
  type ProductCategory,
  type ProductDetail,
} from '../services/products'
import { extractErrorMessage } from '../services/auth'

const PAGE_SIZE = 60

type IconKind = 'all' | 'sun' | 'jar' | 'pump' | 'bottle' | 'dropper' | 'mask' | 'eye' | 'peel' | 'spot' | 'tube'

// Category names come from two source catalogs with different spellings
// ("Serum & Treatment" vs "serum"), so match on keywords.
function kindFor(category: string | null): IconKind {
  const c = (category ?? '').toLowerCase()
  if (!category) return 'all'
  if (c.includes('sun')) return 'sun'
  if (c.includes('moistur') || c.includes('cream')) return 'jar'
  if (c.includes('cleans') || c.includes('wash')) return 'pump'
  if (c.includes('toner') || c.includes('essence') || c.includes('mist')) return 'bottle'
  if (c.includes('serum') || c.includes('treatment') || c.includes('oil')) return 'dropper'
  if (c.includes('mask')) return 'mask'
  if (c.includes('eye')) return 'eye'
  if (c.includes('exfol') || c.includes('peel') || c.includes('scrub')) return 'peel'
  if (c.includes('spot')) return 'spot'
  return 'tube'
}

const TINTS: Record<IconKind, { bg: string; fg: string }> = {
  all: { bg: 'bg-emerald-100', fg: 'text-emerald-700' },
  sun: { bg: 'bg-amber-100', fg: 'text-amber-600' },
  jar: { bg: 'bg-sky-100', fg: 'text-sky-600' },
  pump: { bg: 'bg-cyan-100', fg: 'text-cyan-700' },
  bottle: { bg: 'bg-violet-100', fg: 'text-violet-600' },
  dropper: { bg: 'bg-orange-100', fg: 'text-orange-600' },
  mask: { bg: 'bg-lime-100', fg: 'text-lime-700' },
  eye: { bg: 'bg-indigo-100', fg: 'text-indigo-600' },
  peel: { bg: 'bg-rose-100', fg: 'text-rose-600' },
  spot: { bg: 'bg-pink-100', fg: 'text-pink-600' },
  tube: { bg: 'bg-teal-100', fg: 'text-teal-700' },
}

function tintFor(category: string | null) {
  return TINTS[kindFor(category)]
}

function CategoryIcon({ category, className }: { category: string | null; className?: string }) {
  const kind = kindFor(category)
  return (
    <svg viewBox="0 0 48 48" className={className} fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round" aria-hidden="true">
      {kind === 'all' && (
        <>
          <rect x="7" y="7" width="14" height="14" rx="4" fill="currentColor" fillOpacity="0.25" />
          <rect x="27" y="7" width="14" height="14" rx="4" />
          <rect x="7" y="27" width="14" height="14" rx="4" />
          <rect x="27" y="27" width="14" height="14" rx="4" fill="currentColor" fillOpacity="0.25" />
        </>
      )}
      {kind === 'sun' && (
        <>
          <rect x="10" y="16" width="16" height="26" rx="4" fill="currentColor" fillOpacity="0.25" />
          <rect x="13" y="10" width="10" height="6" rx="1.5" />
          <circle cx="35" cy="14" r="5" />
          <path d="M35 4v2.5M35 21.5V24M25 14h2.5M42.5 14H45M28 7l1.8 1.8M40.2 19.2 42 21M28 21l1.8-1.8M40.2 8.8 42 7" strokeLinecap="round" />
        </>
      )}
      {kind === 'jar' && (
        <>
          <rect x="8" y="12" width="32" height="8" rx="3" />
          <path d="M10 20h28v16a6 6 0 0 1-6 6H16a6 6 0 0 1-6-6V20Z" fill="currentColor" fillOpacity="0.25" />
          <path d="M17 30h14" strokeLinecap="round" />
        </>
      )}
      {kind === 'pump' && (
        <>
          <path d="M20 6h10M25 6v8M19 14h12v6" strokeLinecap="round" />
          <path d="M15 20h20v18a5 5 0 0 1-5 5H20a5 5 0 0 1-5-5V20Z" fill="currentColor" fillOpacity="0.25" />
          <path d="M20 29h10" strokeLinecap="round" />
        </>
      )}
      {kind === 'bottle' && (
        <>
          <rect x="19" y="5" width="10" height="7" rx="1.5" />
          <path d="M17 12h14l3 6v20a5 5 0 0 1-5 5H19a5 5 0 0 1-5-5V18l3-6Z" fill="currentColor" fillOpacity="0.25" />
          <path d="M19 26h10M19 31h10" strokeLinecap="round" />
        </>
      )}
      {kind === 'dropper' && (
        <>
          <path d="M21 4h6a2 2 0 0 1 2 2v8h-10V6a2 2 0 0 1 2-2Z" />
          <rect x="17" y="14" width="14" height="4" rx="1" />
          <path d="M14 18h20v20a5 5 0 0 1-5 5H19a5 5 0 0 1-5-5V18Z" fill="currentColor" fillOpacity="0.25" />
          <path d="M24 26c-2 3-3 4.5-3 6a3 3 0 0 0 6 0c0-1.5-1-3-3-6Z" />
        </>
      )}
      {kind === 'mask' && (
        <>
          <path d="M24 5c9 0 15 7 15 17 0 11-7 21-15 21S9 33 9 22C9 12 15 5 24 5Z" fill="currentColor" fillOpacity="0.25" />
          <path d="M15 20c2-2 5-2 7 0M26 20c2-2 5-2 7 0M19 32c3 2.5 7 2.5 10 0" strokeLinecap="round" />
        </>
      )}
      {kind === 'eye' && (
        <>
          <path d="M4 24s7-12 20-12 20 12 20 12-7 12-20 12S4 24 4 24Z" fill="currentColor" fillOpacity="0.25" />
          <circle cx="24" cy="24" r="6" />
          <circle cx="24" cy="24" r="2" fill="currentColor" />
        </>
      )}
      {kind === 'peel' && (
        <>
          <path d="M12 16h18v22a5 5 0 0 1-5 5h-8a5 5 0 0 1-5-5V16Z" fill="currentColor" fillOpacity="0.25" />
          <rect x="15" y="9" width="12" height="7" rx="1.5" />
          <path d="M37 8v8M33 12h8M38 26v5M35.5 28.5h5" strokeLinecap="round" />
        </>
      )}
      {kind === 'spot' && (
        <>
          <path d="M14 10h20l-2 26a6 6 0 0 1-6 5h-4a6 6 0 0 1-6-5l-2-26Z" fill="currentColor" fillOpacity="0.25" />
          <rect x="18" y="4" width="12" height="6" rx="1.5" />
          <circle cx="24" cy="24" r="3.5" fill="currentColor" />
        </>
      )}
      {kind === 'tube' && (
        <>
          <path d="M14 6h20l-3 30H17L14 6Z" fill="currentColor" fillOpacity="0.25" />
          <rect x="18" y="36" width="12" height="7" rx="1.5" />
          <path d="M18 16h12" strokeLinecap="round" />
        </>
      )}
    </svg>
  )
}

// Catalog descriptions are newline-separated: a summary line, then
// "Label: value" lines, then provenance notes. Lay those out as sections.
const NOTE_LINE = /^(listed in|always check|ingredients? not|source)/i
const LIST_LABEL = /chosen for|good for|key ingredient|suited|concern/i

function ProductDescription({ text }: { text: string }) {
  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean)
  const summary: string[] = []
  const fields: { label: string; value: string }[] = []
  const notes: string[] = []
  for (const line of lines) {
    const m = line.match(/^([A-Z][^:]{2,45}):\s*(.+)$/)
    if (NOTE_LINE.test(line)) notes.push(line)
    else if (m) fields.push({ label: m[1].replace(/\s*\(.*\)\s*$/, ''), value: m[2].replace(/\.$/, '') })
    else summary.push(line)
  }

  return (
    <div className="space-y-4">
      {summary.length > 0 && <p className="text-[15px] leading-relaxed text-slate-700">{summary.join(' ')}</p>}

      {fields.length > 0 && (
        <dl className="grid gap-3 sm:grid-cols-2">
          {fields.map((f) => {
            const asChips = LIST_LABEL.test(f.label)
            const wide = !asChips || f.value.length > 60
            return (
              <div key={f.label} className={`rounded-xl border border-slate-100 bg-slate-50 p-3.5 ${wide ? 'sm:col-span-2' : ''}`}>
                <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{f.label}</dt>
                <dd className="mt-1.5">
                  {asChips ? (
                    <div className="flex flex-wrap gap-1.5">
                      {f.value.split(/,\s*/).filter(Boolean).map((v) => (
                        <span key={v} className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-sm font-medium capitalize text-emerald-800">
                          {v}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm leading-relaxed text-slate-700">{f.value}.</p>
                  )}
                </dd>
              </div>
            )
          })}
        </dl>
      )}

      {notes.length > 0 && (
        <ul className="space-y-1 rounded-xl border border-sky-100 bg-sky-50 px-4 py-3 text-xs leading-relaxed text-sky-900">
          {notes.map((n) => (
            <li key={n} className="flex gap-2">
              <span aria-hidden="true">ℹ</span>
              {n}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function ProductTile({ product: p, onOpen }: { product: Product; onOpen: () => void }) {
  const tint = tintFor(p.category)
  const summary = p.description?.split('\n')[0]
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onOpen())}
      className="group flex cursor-pointer flex-col rounded-xl border border-slate-200 bg-white p-2.5 transition hover:-translate-y-0.5 hover:border-emerald-200 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
    >
      <div className={`relative flex aspect-square items-center justify-center rounded-lg ${tint.bg}`}>
        <CategoryIcon category={p.category} className={`h-1/2 w-1/2 transition-transform group-hover:scale-110 ${tint.fg}`} />
        {p.rating != null && (
          <span className="absolute left-1.5 top-1.5 rounded-md bg-emerald-700 px-1.5 py-0.5 text-[10px] font-semibold text-white">
            ★ {p.rating.toFixed(1)}
          </span>
        )}
        {p.is_sample_data && (
          <span className="absolute right-1.5 top-1.5 text-[10px] text-slate-400">Sample</span>
        )}
      </div>

      {p.category && (
        <p className="mt-2 truncate text-[10px] font-semibold uppercase tracking-wide text-slate-400">{p.category}</p>
      )}
      <p className="mt-0.5 line-clamp-2 h-[2.2rem] text-sm font-semibold leading-[1.1rem] text-slate-900">{p.name}</p>
      {summary && <p className="mt-1 line-clamp-1 text-xs text-slate-500">{summary}</p>}

      <div className="mt-auto flex items-end justify-between gap-2 pt-2.5">
        <p className="min-w-0 truncate text-xs font-medium text-slate-700">{p.brand ?? ''}</p>
        <span className="shrink-0 rounded-lg border border-emerald-600 bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700 transition-colors group-hover:bg-emerald-600 group-hover:text-white">
          VIEW
        </span>
      </div>
    </div>
  )
}

export default function ProductGuide() {
  const location = useLocation()
  const [query, setQuery] = useState('')

  // A search typed in the top bar arrives as router state.
  useEffect(() => {
    const q = (location.state as { q?: string } | null)?.q
    if (q) {
      setQuery(q)
      setCategory(null)
    }
  }, [location.state])
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [category, setCategory] = useState<string | null>(null)
  const [loadingMore, setLoadingMore] = useState(false)
  const [allTotal, setAllTotal] = useState<number | null>(null)

  const [categories, setCategories] = useState<ProductCategory[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [totalCount, setTotalCount] = useState<number | null>(null)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<ProductDetail | null>(null)
  const [dropdownOpen, setDropdownOpen] = useState(false)

  const containerRef = useRef<HTMLDivElement | null>(null)
  const requestId = useRef(0)

  // Load the 9 browseable categories once, up front, so they're ready the
  // instant the search bar is focused.
  useEffect(() => {
    getProductCategories()
      .then(setCategories)
      .catch(() => setCategories([]))
    // Some products sit outside the 9 named categories, so the "All"
    // count can't be the sum of the category counts.
    countProducts()
      .then(setAllTotal)
      .catch(() => setAllTotal(null))
  }, [])

  // Debounce free-text typing so we don't hit the backend on every
  // keystroke; category changes and Clear Filters bypass this entirely.
  useEffect(() => {
    const handle = setTimeout(() => setDebouncedQuery(query.trim()), 300)
    return () => clearTimeout(handle)
  }, [query])

  async function loadMore() {
    const id = requestId.current
    setLoadingMore(true)
    try {
      const next = await searchProducts(
        debouncedQuery || undefined,
        category || undefined,
        PAGE_SIZE,
        products.length,
      )
      if (id === requestId.current) setProducts((prev) => [...prev, ...next])
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoadingMore(false)
    }
  }

  useEffect(() => {
    const id = ++requestId.current
    setLoading(true)
    setError(null)
    Promise.all([
      searchProducts(debouncedQuery || undefined, category || undefined, PAGE_SIZE),
      countProducts(debouncedQuery || undefined, category || undefined),
    ])
      .then(([productList, count]) => {
        if (id !== requestId.current) return
        setProducts(productList)
        setTotalCount(count)
      })
      .catch((err) => {
        if (id !== requestId.current) return
        setError(extractErrorMessage(err))
      })
      .finally(() => {
        if (id === requestId.current) setLoading(false)
      })
  }, [debouncedQuery, category])

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  function pickCategory(name: string) {
    setCategory(name)
    setDropdownOpen(false)
  }

  function clearFilters() {
    setQuery('')
    setDebouncedQuery('')
    setCategory(null)
    setDropdownOpen(false)
  }

  async function openDetail(id: number) {
    setError(null)
    try {
      setSelected(await getProduct(id))
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  const hasFilters = query.trim() !== '' || category !== null
  const showCategoryBrowser = dropdownOpen && query.trim() === ''
  const showSuggestions = dropdownOpen && query.trim() !== '' && products.length > 0

  const allCount = allTotal ?? categories.reduce((sum, c) => sum + c.count, 0)

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Product & Ingredient Guide</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Search by product name, brand or ingredient, or browse by category.
          </p>
        </div>

      <div ref={containerRef} className="relative w-full md:max-w-md">
        <div className="flex gap-2">
          <div className="relative w-full">
            <svg
              viewBox="0 0 24 24"
              className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" strokeLinecap="round" />
            </svg>
            <input
              type="text"
              value={query}
              onFocus={() => setDropdownOpen(true)}
              onChange={(e) => {
                setQuery(e.target.value)
                setDropdownOpen(true)
              }}
              placeholder="Search products, brands or ingredients…"
              className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-3 text-sm shadow-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-100"
            />

            {(showCategoryBrowser || showSuggestions) && (
              <div className="absolute z-10 mt-1 w-full overflow-hidden rounded-md border border-slate-200 bg-white shadow-lg">
                {showCategoryBrowser && (
                  <>
                    <p className="border-b border-slate-100 px-3 py-2 text-xs font-medium uppercase tracking-wide text-slate-400">
                      Browse by category
                    </p>
                    <ul className="max-h-72 overflow-y-auto">
                      {categories.map((c) => (
                        <li key={c.category}>
                          <button
                            type="button"
                            onClick={() => pickCategory(c.category)}
                            className="flex w-full items-center justify-between px-3 py-2 text-left text-sm text-slate-700 hover:bg-emerald-50"
                          >
                            <span>{c.category}</span>
                            <span className="text-xs text-slate-400">{c.count}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </>
                )}

                {showSuggestions && (
                  <>
                    <p className="border-b border-slate-100 px-3 py-2 text-xs font-medium uppercase tracking-wide text-slate-400">
                      Suggestions
                    </p>
                    <ul className="max-h-72 overflow-y-auto">
                      {products.slice(0, 8).map((p) => (
                        <li key={p.id}>
                          <button
                            type="button"
                            onClick={() => {
                              setQuery(p.name)
                              setDebouncedQuery(p.name)
                              setDropdownOpen(false)
                            }}
                            className="flex w-full flex-col px-3 py-2 text-left text-sm hover:bg-emerald-50"
                          >
                            <span className="font-medium text-slate-800">{p.name}</span>
                            {p.brand && <span className="text-xs text-slate-500">{p.brand}</span>}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            )}
          </div>

        </div>
      </div>
      </div>

      {error && (
        <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
          {error}
        </p>
      )}

      <div className="flex h-[calc(100vh-13rem)] min-h-[30rem] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        {/* Category sidebar */}
        <nav aria-label="Categories" className="w-20 shrink-0 overflow-y-auto border-r border-slate-100 sm:w-28">
          {[{ category: null as string | null, count: allCount }, ...categories].map((c) => {
            const active = category === c.category
            return (
              <button
                key={c.category ?? 'all'}
                type="button"
                onClick={() => (c.category ? pickCategory(c.category) : setCategory(null))}
                className={`relative flex w-full flex-col items-center gap-1 px-1.5 py-3 text-center transition-colors ${
                  active ? 'bg-emerald-50' : 'hover:bg-slate-50'
                }`}
              >
                <span
                  className={`flex h-12 w-12 items-center justify-center rounded-xl transition-transform sm:h-14 sm:w-14 ${
                    tintFor(c.category).bg
                  } ${active ? 'scale-105' : ''}`}
                >
                  <CategoryIcon category={c.category} className={`h-8 w-8 sm:h-9 sm:w-9 ${tintFor(c.category).fg}`} />
                </span>
                <span
                  className={`text-[11px] leading-tight sm:text-xs ${
                    active ? 'font-semibold text-emerald-900' : 'text-slate-600'
                  }`}
                >
                  {c.category ?? 'All products'}
                </span>
                <span className="text-[10px] text-slate-400">{c.count}</span>
                {active && <span className="absolute inset-y-2 right-0 w-1 rounded-l-full bg-emerald-600" />}
              </button>
            )
          })}
        </nav>

        {/* Products */}
        <section className="flex min-w-0 flex-1 flex-col">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
            <div>
              <h2 className="font-semibold text-slate-900">{category ?? 'All products'}</h2>
              {totalCount !== null && (
                <p className="text-xs text-slate-500">
                  {totalCount} product{totalCount === 1 ? '' : 's'}
                  {query.trim() && <> matching “{query.trim()}”</>}
                </p>
              )}
            </div>
            {hasFilters && (
              <button
                type="button"
                onClick={clearFilters}
                className="rounded-full border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
              >
                Clear filters ✕
              </button>
            )}
          </div>

          <div className="flex-1 overflow-y-auto bg-slate-50/60 p-3 sm:p-4">
            {loading && products.length === 0 ? (
              <p className="py-12 text-center text-slate-400">Loading products…</p>
            ) : products.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-slate-500">
                No products found. Try another search or category.
              </div>
            ) : (
              <>
                <div
                  className={`grid grid-cols-2 gap-3 transition-opacity sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 ${
                    loading ? 'opacity-50' : ''
                  }`}
                >
                  {products.map((p) => (
                    <ProductTile key={p.id} product={p} onOpen={() => openDetail(p.id)} />
                  ))}
                </div>
                {!loading && totalCount !== null && totalCount > products.length && (
                  <div className="mt-5 text-center">
                    <button
                      type="button"
                      disabled={loadingMore}
                      onClick={loadMore}
                      className="rounded-full border border-emerald-600 bg-white px-5 py-2 text-sm font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
                    >
                      {loadingMore ? 'Loading…' : `Load more (${totalCount - products.length} left)`}
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </section>
      </div>

      {selected && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setSelected(null)}
        >
          <div
            className="flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-white shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-6 py-5">
              <div>
                <h2 className="text-xl font-semibold leading-snug text-slate-900">{selected.name}</h2>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  {selected.brand && <span className="text-sm font-medium text-slate-600">{selected.brand}</span>}
                  {selected.category && (
                    <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
                      {selected.category}
                    </span>
                  )}
                  {selected.rating != null && (
                    <span className="text-sm font-medium text-amber-600">★ {selected.rating.toFixed(1)}</span>
                  )}
                  {selected.is_sample_data && (
                    <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-700">
                      Sample data
                    </span>
                  )}
                </div>
              </div>
              <button
                onClick={() => setSelected(null)}
                className="shrink-0 rounded-full p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                aria-label="Close"
              >
                ✕
              </button>
            </div>

            <div className="space-y-6 overflow-y-auto px-6 py-5">
              {selected.description && <ProductDescription text={selected.description} />}

              {(() => {
                const skinTypes: { label: string; suited: boolean | null }[] = [
                  { label: 'Dry', suited: selected.suitable_dry },
                  { label: 'Normal', suited: selected.suitable_normal },
                  { label: 'Oily', suited: selected.suitable_oily },
                  { label: 'Combination', suited: selected.suitable_combination },
                  { label: 'Sensitive', suited: selected.suitable_sensitive },
                ]
                const stated = skinTypes.filter((s) => s.suited !== null)
                if (stated.length === 0) return null
                return (
                  <div>
                    <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Suitable for</h3>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {stated.map((s) => (
                        <span
                          key={s.label}
                          className={
                            s.suited
                              ? 'rounded-full bg-emerald-100 px-3 py-1 text-sm font-medium text-emerald-700'
                              : 'rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-400 line-through'
                          }
                        >
                          {s.label}
                        </span>
                      ))}
                    </div>
                  </div>
                )
              })()}

              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
                  Ingredients{selected.ingredient_count != null && ` · ${selected.ingredient_count}`}
                </h3>

                {selected.ingredients.length > 0 ? (
                  <ul className="mt-2 space-y-2">
                    {selected.ingredients.map((ing) => (
                      <li key={ing.id} className="rounded-xl border border-slate-100 bg-slate-50 p-4 text-sm">
                        <p className="text-base font-semibold text-slate-900">{ing.name}</p>
                        {ing.description &&
                          ing.description
                            .split(/\n\s*\n|\n/)
                            .map((part) => part.trim())
                            .filter(Boolean)
                            .map((part, i) => {
                              const labelled = part.match(/^([A-Z][^:]{2,40}):\s*(.+)$/s)
                              return labelled ? (
                                <div key={i} className="mt-2.5">
                                  <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{labelled[1]}</p>
                                  <p className="mt-0.5 leading-relaxed text-slate-600">{labelled[2]}</p>
                                </div>
                              ) : (
                                <p key={i} className="mt-1 leading-relaxed text-slate-600">
                                  {part}
                                </p>
                              )
                            })}
                        {ing.precautions && (
                          <div className="mt-3 flex gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-amber-800">
                            <span aria-hidden="true">⚠</span>
                            <div>
                              <p className="text-[11px] font-semibold uppercase tracking-wide">Caution</p>
                              <p className="mt-0.5 leading-relaxed">{ing.precautions}</p>
                            </div>
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : selected.ingredients_list ? (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {selected.ingredients_list
                      .split('|')
                      .map((part) => part.trim())
                      .filter(Boolean)
                      .map((ingredient, i) => (
                        <span
                          key={`${ingredient}-${i}`}
                          className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-sm text-slate-700"
                        >
                          {ingredient}
                        </span>
                      ))}
                  </div>
                ) : selected.ingredients_text ? (
                  <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-slate-600">
                    {selected.ingredients_text}
                  </p>
                ) : (
                  <p className="mt-2 text-sm text-slate-400">No ingredients listed.</p>
                )}
              </div>
            </div>

            {selected.source && (
              <p className="border-t border-slate-100 px-6 py-3 text-xs leading-relaxed text-slate-400">
                Source: {selected.source}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
