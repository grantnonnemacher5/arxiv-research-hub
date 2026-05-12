import { useEffect, useState } from 'react'
import { getPipelineRuns } from '../api'
import { friendlyErrorMessage } from '../lib/apiErrors.js'

export default function PipelineRuns({ refreshKey }) {
  const [runs, setRuns] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setErr(null)
      try {
        const data = await getPipelineRuns(30)
        if (!cancelled) setRuns(data)
      } catch (e) {
        if (!cancelled) setErr(friendlyErrorMessage(e?.message || e))
      }
    })()
    return () => {
      cancelled = true
    }
  }, [refreshKey])

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <h2 className="font-serif text-lg font-semibold text-slate-900">Pipeline runs</h2>
      <p className="mt-1 text-sm text-slate-500">
        Recent sync jobs — duration, saved vs skipped duplicates, and failures (manual + scheduled).
      </p>
      {err && (
        <p className="mt-3 text-sm text-red-700" role="alert">
          {err}
        </p>
      )}
      {!err && runs && runs.length === 0 && (
        <p className="mt-4 text-sm text-slate-500">No runs recorded yet. Run &quot;Sync arXiv&quot; once.</p>
      )}
      {!err && runs && runs.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <th className="py-2 pr-3">Finished</th>
                <th className="py-2 pr-3">Trigger</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2 pr-2 text-right">Saved</th>
                <th className="py-2 pr-2 text-right">Skipped</th>
                <th className="py-2 pr-2 text-right">Backfill</th>
                <th className="py-2 pr-2 text-right">ms</th>
                <th className="py-2">Error</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} className="border-b border-slate-100 last:border-0">
                  <td className="py-2 pr-3 font-mono text-xs text-slate-700">
                    {r.finished_at ? formatLocal(r.finished_at) : '—'}
                  </td>
                  <td className="py-2 pr-3 text-slate-700">{r.trigger}</td>
                  <td className="py-2 pr-3">
                    <span
                      className={
                        r.status === 'completed'
                          ? 'rounded-md bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-900'
                          : 'rounded-md bg-red-100 px-2 py-0.5 text-xs font-medium text-red-900'
                      }
                    >
                      {r.status}
                    </span>
                  </td>
                  <td className="py-2 pr-2 text-right tabular-nums text-slate-800">{r.saved}</td>
                  <td className="py-2 pr-2 text-right tabular-nums text-slate-800">{r.skipped_duplicates}</td>
                  <td className="py-2 pr-2 text-right tabular-nums text-slate-800">{r.backfilled}</td>
                  <td className="py-2 pr-2 text-right tabular-nums text-slate-600">{r.duration_ms}</td>
                  <td className="max-w-[200px] truncate py-2 text-xs text-red-800" title={r.error || ''}>
                    {r.error || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function formatLocal(iso) {
  try {
    const d = new Date(iso)
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}
