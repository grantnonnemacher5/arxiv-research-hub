import { useEffect, useMemo, useRef, useState } from 'react'
import { getPapers } from '../api'
import { friendlyErrorMessage } from '../lib/apiErrors.js'
import { PAGE_CARD } from '../constants/layout.js'
import CategoryBadge from './CategoryBadge.jsx'
import PaperDetailDrawer from './PaperDetailDrawer.jsx'

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100]

/** Values must match `classifier.BUCKET_DESCRIPTIONS` keys and the stats cards. */
const BUCKET_FILTERS = [
  { value: null, label: 'All' },
  { value: 'General AI', label: 'General AI' },
  { value: 'Autonomous Agents', label: 'Agents' },
  { value: 'AI x Finance', label: 'Finance' },
]

function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export default function PaperList({ refreshKey, onToast }) {
  const onToastRef = useRef(onToast)

  useEffect(() => {
    onToastRef.current = onToast
  }, [onToast])

  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [bucketFilter, setBucketFilter] = useState(null)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [selectedPaper, setSelectedPaper] = useState(null)

  useEffect(() => {
    const t = setTimeout(() => {
      setDebounced(q.trim())
      setPage(1)
    }, 350)
    return () => clearTimeout(t)
  }, [q])

  useEffect(() => {
    const id = requestAnimationFrame(() => setPage(1))
    return () => cancelAnimationFrame(id)
  }, [refreshKey])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      onToastRef.current?.(null)
      try {
        const res = await getPapers({
          page,
          pageSize,
          bucket: bucketFilter || undefined,
          q: debounced || undefined,
        })
        if (!cancelled) setData(res)
      } catch (e) {
        if (!cancelled) {
          setData(null)
          onToastRef.current?.({ type: 'err', text: friendlyErrorMessage(e?.message || e) })
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [page, pageSize, bucketFilter, debounced, refreshKey])

  const totalPages = useMemo(() => {
    if (!data?.total || !data?.page_size) return 1
    return Math.max(1, Math.ceil(data.total / data.page_size))
  }, [data])

  const badgesFor = (buckets) =>
    (buckets || '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)

  return (
    <section className={`flex w-full min-h-0 flex-col ${PAGE_CARD}`}>
      <div className="border-b border-slate-100 pb-5 text-left">
        <h2 className="font-serif text-lg font-semibold text-slate-900">Browse papers</h2>
        <p className="mt-1 text-sm text-slate-500">
          Filter by bucket or title — paginated list of everything ingested.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-2 sm:gap-3">
          <div className="flex flex-wrap gap-2" role="group" aria-label="Filter papers by bucket">
          {BUCKET_FILTERS.map(({ value, label }) => {
            const active = bucketFilter === value
            return (
              <button
                key={value ?? 'all'}
                type="button"
                aria-pressed={active}
                onClick={() => {
                  setBucketFilter(value)
                  setPage(1)
                }}
                className={`rounded-lg border-2 px-3 py-1.5 text-xs font-semibold shadow-sm transition sm:text-sm ${
                  active
                    ? 'border-sky-600 bg-sky-500 text-white hover:bg-sky-600'
                    : 'border-slate-300 bg-slate-50 text-slate-800 hover:border-slate-400 hover:bg-slate-100'
                }`}
              >
                {label}
              </button>
            )
          })}
          </div>
          <label className="relative block min-w-[min(100%,220px)] flex-1 sm:min-w-[280px]">
            <span className="sr-only">Filter library</span>
            <svg
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden
            >
              <circle cx="11" cy="11" r="7" />
              <path d="M21 21l-4.3-4.3" strokeLinecap="round" />
            </svg>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Title, authors, arXiv id…"
              className="w-full rounded-xl border border-slate-200 bg-slate-50/90 py-2.5 pl-10 pr-3 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-sky-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
              type="search"
              autoComplete="off"
            />
          </label>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col">
        {loading && (
          <div className="flex items-center gap-2 py-10 text-sm text-slate-500">
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-sky-500" />
            Loading…
          </div>
        )}

        {!loading && data && (
          <>
          <div className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-left text-xs text-slate-500">
              Page <span className="font-mono text-slate-700">{data.page}</span> of{' '}
              <span className="font-mono text-slate-700">{totalPages}</span>
              <span className="mx-2 text-slate-300">·</span>
              <span className="text-slate-600">{data.total}</span> total
            </p>
            <label className="flex items-center justify-end gap-2 sm:justify-end">
              <span className="text-xs font-medium text-slate-500">Rows per page</span>
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value))
                  setPage(1)
                }}
                className="cursor-pointer rounded-lg border border-slate-200 bg-white py-1.5 pl-3 pr-8 text-sm font-medium text-slate-700 shadow-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                aria-label="Rows per page"
              >
                {PAGE_SIZE_OPTIONS.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <ul className="space-y-3">
            {data.items.map((p) => {
              const tags = badgesFor(p.buckets)
              return (
                <li key={p.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedPaper(p)}
                    className="w-full rounded-xl border border-slate-100 bg-slate-50/50 p-4 text-left shadow-sm transition hover:border-sky-200 hover:bg-white hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-400"
                  >
                    <div className="flex flex-wrap items-start gap-2">
                      {tags.length > 0 ? (
                        tags.map((b) => <CategoryBadge key={b} label={b} />)
                      ) : (
                        <CategoryBadge label="Unclassified" />
                      )}
                    </div>
                    <h3 className="mt-3 text-lg font-semibold leading-snug tracking-tight text-slate-900 sm:text-xl">
                      {p.title}
                    </h3>
                    <p className="mt-2 text-sm font-medium leading-relaxed text-slate-600">{p.authors}</p>
                    <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1 font-mono text-[11px] text-slate-400">
                      <span>{formatDate(p.published_date)}</span>
                      <span className="text-slate-300" aria-hidden>
                        ·
                      </span>
                      <span className="text-slate-400">{p.arxiv_id}</span>
                    </div>
                  </button>
                </li>
              )
            })}
          </ul>

          <div className="mt-4 flex justify-between border-t border-slate-100 pt-4">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((pg) => Math.max(1, pg - 1))}
              className="rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-30"
            >
              ← Previous
            </button>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => setPage((pg) => pg + 1)}
              className="rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-30"
            >
              Next →
            </button>
          </div>
          </>
        )}
      </div>

      <PaperDetailDrawer paper={selectedPaper} onClose={() => setSelectedPaper(null)} />
    </section>
  )
}
