/** Short copy for dashboard KPI + tooltip. */
export const PIPELINE_SUCCESS_HINT =
  'Finished sync runs only (last 30). Completed = success. Stopped and Failed lower the rate. Runs still in progress are excluded.'

/** Aggregate ingest run rows for dashboard KPIs. */
export function computePipelineSuccess(items) {
  const finished = (items ?? []).filter((r) =>
    ['completed', 'failed', 'cancelled'].includes(r.status),
  )
  const completed = finished.filter((r) => r.status === 'completed').length
  const total = finished.length
  const pct = total > 0 ? Math.round((100 * completed) / total) : null
  return { pct, completed, total }
}

export function formatDurationMs(ms) {
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

export function pipelineStatusLabel(status) {
  switch (status) {
    case 'completed':
      return 'Completed'
    case 'running':
      return 'Running'
    case 'failed':
      return 'Failed'
    case 'cancelled':
      return 'Stopped'
    default:
      return status || '—'
  }
}
