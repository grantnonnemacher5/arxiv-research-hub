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

/** Readable lines for the Reports list; new filenames embed paper-from / paper-to. */
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
    <aside className="flex h-full min-h-0 w-full flex-col rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <h2 className="font-serif text-lg font-semibold text-slate-900">Reports</h2>
      <p className="mt-1 text-sm text-slate-500">Generated HTML files.</p>

      <div className="mt-5 flex min-h-0 flex-1 flex-col">
        {loading && (
          <div className="flex flex-1 items-center justify-center py-16">
            <div
              className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-sky-500"
              aria-hidden
            />
          </div>
        )}

        {!loading && rows.length === 0 && (
          <div className="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50/80 px-4 py-16 text-center">
            <p className="text-sm text-slate-500">Nothing generated yet.</p>
            <p className="mt-2 max-w-xs text-xs text-slate-400">
              Use Export report above to create HTML files; they will appear here.
            </p>
          </div>
        )}

        {!loading && rows.length > 0 && (
          <ul className="max-h-[min(28rem,50vh)] flex-1 space-y-1 overflow-y-auto pr-1">
            {rows.slice(0, 20).map((r) => {
              const meta = reportListMeta(r)
              return (
              <li
                key={r.id}
                className="flex items-center justify-between gap-2 rounded-lg py-2 pl-1 pr-0 hover:bg-slate-50"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-800" title={meta.filename}>
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
                  className="shrink-0 rounded-md px-2 py-1 text-xs font-semibold text-sky-600 hover:bg-sky-50 hover:text-sky-700"
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
    </aside>
  )
}
