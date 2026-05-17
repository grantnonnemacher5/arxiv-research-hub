import { useEffect, useRef, useState } from 'react'
import { apiUrl, listReports } from '../api'
import { friendlyErrorMessage } from '../lib/apiErrors.js'

const PERIOD_LABELS = {
  '7d': 'Last 7 days',
  '1m': 'Last 30 days',
  '3m': 'Last 90 days',
  '6m': 'Last 6 months',
  '1y': 'Last 12 months',
}

function formatShortDate(isoDate) {
  if (!isoDate) return ''
  const d = new Date(`${isoDate}T12:00:00Z`)
  if (Number.isNaN(d.getTime())) return isoDate
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatExported(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function reportListMeta(r) {
  const windowLabel = PERIOD_LABELS[r.period] || `Window ${r.period}`
  const exported = formatExported(r.generated_at)
  const m = r.filename?.match(/papers-(\d{4}-\d{2}-\d{2})-to-(\d{4}-\d{2}-\d{2})/)
  const primary = `AI themes · ${windowLabel}`
  if (m) {
    const paperRange = `Papers ${formatShortDate(m[1])} – ${formatShortDate(m[2])}`
    const secondary = exported ? `${paperRange} · Exported ${exported}` : paperRange
    return { primary, secondary, filename: r.filename }
  }
  const secondary = exported ? `Exported ${exported}` : null
  return { primary, secondary, filename: r.filename }
}

function EmptyIcon() {
  return (
    <svg className="h-10 w-10 text-slate-300" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="M14 2v6h6M8 13h8M8 17h5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

export default function ReportViewer({ refreshKey, onToast }) {
  const onToastRef = useRef(onToast)

  useEffect(() => {
    onToastRef.current = onToast
  }, [onToast])

  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        const data = await listReports()
        if (!cancelled) setRows(Array.isArray(data) ? data : [])
      } catch (e) {
        if (!cancelled) {
          setRows([])
          onToastRef.current?.({ type: 'err', text: friendlyErrorMessage(e?.message || e) })
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [refreshKey])

  return (
    <div className="rounded-xl border border-slate-200/80 bg-white shadow-[0_1px_3px_rgba(15,23,42,0.06)]">
      {loading && (
        <div className="flex items-center justify-center gap-2 py-10 text-sm text-slate-500">
          <span
            className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-slate-200 border-t-sky-500"
            aria-hidden
          />
          Loading reports…
        </div>
      )}

      {!loading && rows.length === 0 && (
        <div className="flex flex-col items-center justify-center px-4 py-10 text-center sm:px-6">
          <EmptyIcon />
          <p className="mt-3 text-sm text-slate-500">No reports yet — generate one above</p>
        </div>
      )}

      {!loading && rows.length > 0 && (
        <ul className="max-h-[min(28rem,50vh)] divide-y divide-slate-100 overflow-y-auto">
          {rows.map((r) => {
            const meta = reportListMeta(r)
            return (
              <li
                key={r.id}
                className="flex items-center justify-between gap-3 px-4 py-3 first:pt-3.5 last:pb-3.5 hover:bg-slate-50/80"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-900" title={meta.filename}>
                    {meta.primary}
                  </p>
                  {meta.secondary ? (
                    <p className="mt-0.5 truncate text-xs text-slate-600">{meta.secondary}</p>
                  ) : null}
                  <p className="mt-0.5 truncate font-mono text-[11px] text-slate-400" title={meta.filename}>
                    {meta.filename}
                  </p>
                </div>
                <a
                  className="shrink-0 rounded-md px-2.5 py-1 text-xs font-semibold text-sky-700 hover:bg-sky-50"
                  href={apiUrl(`/reports/${encodeURIComponent(r.filename)}`)}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open
                </a>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
