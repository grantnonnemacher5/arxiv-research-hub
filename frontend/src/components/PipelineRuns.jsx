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
        Recent sync jobs — <strong className="font-medium text-slate-600">Saved</strong> is new papers;
        <strong className="font-medium text-slate-600"> skipped</strong> means that arXiv id was already
        in your library. Completed + 0 saved usually means the fetched batch was all duplicates, not a
        failed sync.
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
        <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200">
          <table className="w-full min-w-[720px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-600">
                <th className="border-r border-slate-200 px-3 py-2.5">Finished</th>
                <th className="border-r border-slate-200 px-3 py-2.5">Trigger</th>
                <th className="border-r border-slate-200 px-3 py-2.5">Status</th>
                <th className="border-r border-slate-200 px-3 py-2.5 text-right">Saved</th>
                <th className="border-r border-slate-200 px-3 py-2.5 text-right">Skipped</th>
                <th className="border-r border-slate-200 px-3 py-2.5 text-right">Backfill</th>
                <th className="border-r border-slate-200 px-3 py-2.5 text-right">Duration</th>
                <th className="px-3 py-2.5">Error</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr
                  key={r.id}
                  className="border-b border-slate-100 odd:bg-white even:bg-slate-50/60 last:border-b-0"
                >
                  <td className="border-r border-slate-200 px-3 py-2.5 font-mono text-xs text-slate-700">
                    {r.finished_at ? formatLocal(r.finished_at) : '—'}
                  </td>
                  <td className="border-r border-slate-200 px-3 py-2.5 text-slate-700">{r.trigger}</td>
                  <td className="border-r border-slate-200 px-3 py-2.5">
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
                  <td className="border-r border-slate-200 px-3 py-2.5 text-right tabular-nums text-slate-800">
                    {r.saved}
                  </td>
                  <td className="border-r border-slate-200 px-3 py-2.5 text-right tabular-nums text-slate-800">
                    {r.skipped_duplicates}
                  </td>
                  <td className="border-r border-slate-200 px-3 py-2.5 text-right tabular-nums text-slate-800">
                    {r.backfilled}
                  </td>
                  <td
                    className="border-r border-slate-200 px-3 py-2.5 text-right text-slate-700"
                    title={r.duration_ms != null ? `${r.duration_ms.toLocaleString()} ms` : ''}
                  >
                    <span className="tabular-nums">{formatDurationMs(r.duration_ms)}</span>
                  </td>
                  <td className="max-w-[220px] truncate px-3 py-2.5 text-xs text-red-800" title={r.error || ''}>
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

/** Human-readable run length; hover shows exact ms for ops. */
function formatDurationMs(ms) {
  if (ms == null || Number.isNaN(ms) || ms < 0) return '—'
  const n = Math.floor(Number(ms))
  if (n < 1000) return `${n} ms`
  const sec = Math.floor(n / 1000)
  if (sec < 60) return `${sec}s`
  const min = Math.floor(sec / 60)
  const s = sec % 60
  if (min < 60) return `${min}m ${s}s`
  const h = Math.floor(min / 60)
  const m = min % 60
  return `${h}h ${m}m`
}
