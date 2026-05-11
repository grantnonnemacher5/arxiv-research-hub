import { useEffect, useRef, useState } from 'react'
import { apiUrl, listReports } from '../api'
import { friendlyErrorMessage } from '../lib/apiErrors.js'

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
            {rows.slice(0, 20).map((r) => (
              <li
                key={r.id}
                className="flex items-center justify-between gap-2 rounded-lg py-2 pl-1 pr-0 hover:bg-slate-50"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs text-slate-600">{r.filename}</p>
                  <p className="text-[11px] text-slate-400">{r.period}</p>
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
            ))}
          </ul>
        )}
      </div>
    </aside>
  )
}
