import { useEffect, useState } from 'react'
import { getStats, runPipeline } from '../api'
import { friendlyErrorMessage } from '../lib/apiErrors.js'
import PaperList from './PaperList.jsx'
import PaperSearch from './PaperSearch.jsx'
import PipelineRuns from './PipelineRuns.jsx'
import ReportButtons from './ReportButtons.jsx'
import ReportViewer from './ReportViewer.jsx'

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [toast, setToast] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [pipelineLoading, setPipelineLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const s = await getStats()
        if (!cancelled) setStats(s)
      } catch (e) {
        if (!cancelled)
          setToast({ type: 'err', text: friendlyErrorMessage(e?.message || e) })
      }
    })()
    return () => {
      cancelled = true
    }
  }, [refreshKey])

  async function handlePipeline() {
    setPipelineLoading(true)
    setToast(null)
    try {
      const res = await runPipeline()
      setToast({
        type: 'ok',
        text: `Done — saved ${res.stats?.saved ?? 0}, skipped ${res.stats?.skipped_duplicates ?? 0}, backfilled ${res.stats?.backfilled ?? 0}`,
      })
      setRefreshKey((k) => k + 1)
    } catch (e) {
      setToast({ type: 'err', text: friendlyErrorMessage(e?.message || e) })
    } finally {
      setPipelineLoading(false)
    }
  }

  const buckets = stats?.buckets || {}

  return (
    <div className="relative z-10 mx-auto w-full max-w-[min(1400px,96vw)] px-4 pb-16 pt-8 sm:px-6 lg:px-8">
      <header className="mb-10 flex flex-col gap-6 border-b border-slate-200 pb-8 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-sky-600">Local · arXiv</p>
          <h1 className="mt-1 font-serif text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
            Research hub
          </h1>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-500">
            Sync papers, review themes, export HTML reports for a chosen window.
          </p>
        </div>
        <button
          type="button"
          disabled={pipelineLoading}
          onClick={handlePipeline}
          className="inline-flex h-11 shrink-0 items-center justify-center gap-2 self-start rounded-lg bg-sky-500 px-6 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-600 disabled:opacity-50 sm:self-auto"
        >
          {pipelineLoading ? (
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
          ) : null}
          {pipelineLoading ? 'Syncing…' : 'Sync arXiv'}
        </button>
      </header>

      {toast && (
        <div
          role="status"
          className={`mb-10 rounded-lg border px-4 py-3 text-sm ${
            toast.type === 'ok'
              ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
              : 'border-red-200 bg-red-50 text-red-900'
          }`}
        >
          {toast.text}
        </div>
      )}

      <div className="mb-10 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 lg:gap-4">
        <Stat variant="blue" label="Total papers" value={stats?.total_papers ?? '—'} />
        <Stat variant="green" label="Today" value={stats?.papers_today ?? '—'} />
        <Stat variant="purple" label="General AI" value={buckets['General AI'] ?? '—'} />
        <Stat variant="orange" label="Agents" value={buckets['Autonomous Agents'] ?? '—'} />
        <Stat variant="teal" label="Finance" value={buckets['AI x Finance'] ?? '—'} />
      </div>

      <div className="mb-10">
        <PaperSearch />
      </div>

      <div className="mb-10">
        <PipelineRuns refreshKey={refreshKey} />
      </div>

      <section className="mb-10 rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <h2 className="font-serif text-lg font-semibold text-slate-900">Export report</h2>
        <p className="mt-1 text-sm text-slate-500">
          Pick a window — the HTML report opens in a new tab when ready.
        </p>
        <div className="mt-4">
          <ReportButtons onToast={setToast} onReportDone={() => setRefreshKey((k) => k + 1)} />
        </div>
      </section>

      <div className="mb-10 grid gap-8 lg:grid-cols-5 lg:items-stretch">
        <div className="flex h-full min-h-0 lg:col-span-3">
          <PaperList refreshKey={refreshKey} onToast={setToast} />
        </div>
        <div className="flex h-full min-h-0 lg:col-span-2">
          <ReportViewer refreshKey={refreshKey} onToast={setToast} />
        </div>
      </div>
    </div>
  )
}

const STAT_VARIANTS = {
  blue: 'border-sky-200 bg-gradient-to-br from-sky-50 to-white ring-1 ring-sky-100/80',
  green: 'border-emerald-200 bg-gradient-to-br from-emerald-50 to-white ring-1 ring-emerald-100/80',
  purple: 'border-violet-200 bg-gradient-to-br from-violet-50 to-white ring-1 ring-violet-100/80',
  orange: 'border-orange-200 bg-gradient-to-br from-orange-50 to-white ring-1 ring-orange-100/80',
  teal: 'border-teal-200 bg-gradient-to-br from-teal-50 to-white ring-1 ring-teal-100/80',
}

const STAT_LABEL = {
  blue: 'text-sky-800',
  green: 'text-emerald-800',
  purple: 'text-violet-800',
  orange: 'text-orange-800',
  teal: 'text-teal-800',
}

function Stat({ label, value, variant = 'blue' }) {
  const shell = STAT_VARIANTS[variant] || STAT_VARIANTS.blue
  const lab = STAT_LABEL[variant] || STAT_LABEL.blue
  return (
    <div className={`rounded-xl border px-4 py-5 shadow-sm sm:px-5 sm:py-6 ${shell}`}>
      <p className={`text-xs font-semibold uppercase tracking-wide ${lab}`}>{label}</p>
      <p className="mt-2 font-serif text-4xl font-bold tabular-nums leading-none tracking-tight text-slate-900 sm:text-5xl">
        {value}
      </p>
    </div>
  )
}
