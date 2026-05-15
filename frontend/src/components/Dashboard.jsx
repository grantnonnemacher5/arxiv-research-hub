import { useEffect, useRef, useState } from 'react'
import { cancelPipeline, getPipelineBusy, getPipelineRuns, getStats, runPipeline } from '../api'
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
  const [syncInProgress, setSyncInProgress] = useState(false)
  const [cancelLoading, setCancelLoading] = useState(false)
  const pipelinePollRef = useRef(null)
  /** True once we have seen either in-memory busy or a DB `running` row (works across API workers). */
  const pipelineEverSawActiveRef = useRef(false)
  /** Consecutive polls with no active signal after we had seen active (debounce end detection). */
  const pipelineIdleStreakRef = useRef(0)
  const pipelineWatchStartedAtRef = useRef(0)

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

  useEffect(() => {
    return () => {
      stopPipelineSyncWatch()
    }
  }, [])

  function stopPipelineSyncWatch() {
    if (pipelinePollRef.current) {
      clearInterval(pipelinePollRef.current)
      pipelinePollRef.current = null
    }
  }

  /**
   * Keep Stop visible until the pipeline is clearly finished.
   * Uses DB `running` rows — not only `GET /pipeline-status` — so multi-worker APIs still work.
   */
  function startPipelineSyncWatch() {
    stopPipelineSyncWatch()
    pipelineEverSawActiveRef.current = false
    pipelineIdleStreakRef.current = 0
    pipelineWatchStartedAtRef.current = Date.now()

    const pollMs = 1600

    const tick = async () => {
      try {
        let busy = false
        try {
          const b = await getPipelineBusy()
          busy = !!b?.busy
        } catch {
          /* ignore — may be a different worker than the one holding the lock */
        }

        let hasRunning = false
        try {
          const runsPayload = await getPipelineRuns({ page: 1, pageSize: 20 })
          hasRunning = (runsPayload?.items ?? []).some((r) => r.status === 'running')
        } catch {
          /* transient network error — don't kill the watch, try again next tick */
        }

        setRefreshKey((k) => k + 1)

        const active = busy || hasRunning

        if (active) {
          pipelineEverSawActiveRef.current = true
          pipelineIdleStreakRef.current = 0
          return
        }

        if (!pipelineEverSawActiveRef.current) {
          const waitedMs = Date.now() - pipelineWatchStartedAtRef.current
          if (waitedMs > 120_000) {
            stopPipelineSyncWatch()
            setSyncInProgress(false)
            setToast({
              type: 'ok',
              text: 'Could not confirm the sync on the server — check Pipeline runs.',
            })
          }
          return
        }

        pipelineIdleStreakRef.current += 1
        if (pipelineIdleStreakRef.current < 2) return

        stopPipelineSyncWatch()
        setSyncInProgress(false)
        let toastType = 'ok'
        let text = 'Sync finished — stats and runs updated.'
        try {
          const data = await getPipelineRuns({ page: 1, pageSize: 1 })
          const st = data?.items?.[0]?.status
          if (st === 'cancelled') {
            text =
              'Sync cancelled. Anything already saved stays in your library — see Pipeline runs.'
          } else if (st === 'failed') {
            toastType = 'err'
            text = 'Sync ended with an error — see Pipeline runs for details.'
          }
        } catch {
          /* keep default */
        }
        setToast({ type: toastType, text })
      } catch {
        /* Never tear down the watch on unexpected errors — leave Stop available. */
      }
    }

    void tick()
    pipelinePollRef.current = setInterval(tick, pollMs)
  }

  async function handleCancelPipeline() {
    setCancelLoading(true)
    setToast(null)
    try {
      await cancelPipeline()
      setToast({
        type: 'ok',
        text: 'Stop requested — ingest stops after the current paper (if any).',
      })
    } catch (e) {
      setToast({ type: 'err', text: friendlyErrorMessage(e?.message || e) })
    } finally {
      setCancelLoading(false)
    }
  }

  async function handlePipeline() {
    setPipelineLoading(true)
    setToast(null)
    try {
      const res = await runPipeline()
      if (res.status === 'accepted') {
        stopPipelineSyncWatch()
        setSyncInProgress(true)
        startPipelineSyncWatch()
        setToast({
          type: 'ok',
          text:
            res.message ||
            'Sync started on the server. Use Stop sync to cancel; stats refresh while the job runs.',
        })
        setRefreshKey((k) => k + 1)
        return
      }
      const saved = res.stats?.saved ?? 0
      const skipped = res.stats?.skipped_duplicates ?? 0
      const backfilled = res.stats?.backfilled ?? 0
      let text = `Done — saved ${saved}, skipped ${skipped} (already in library), backfilled ${backfilled}.`
      if (saved === 0 && skipped > 0) {
        text += ' Totals unchanged: every id in this fetch was already ingested.'
      }
      setToast({ type: 'ok', text })
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
        <div className="flex shrink-0 flex-col gap-2 self-start sm:flex-row sm:self-auto">
          <button
            type="button"
            disabled={pipelineLoading || syncInProgress}
            onClick={handlePipeline}
            className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-sky-500 px-6 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-600 disabled:opacity-50"
          >
            {pipelineLoading ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
            ) : null}
            {pipelineLoading ? 'Starting…' : syncInProgress ? 'Sync running' : 'Sync arXiv'}
          </button>
          {syncInProgress ? (
            <button
              type="button"
              disabled={cancelLoading}
              onClick={handleCancelPipeline}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-5 text-sm font-semibold text-slate-800 shadow-sm transition hover:bg-slate-50 disabled:opacity-50"
            >
              {cancelLoading ? (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-700" />
              ) : null}
              {cancelLoading ? 'Stopping…' : 'Stop sync'}
            </button>
          ) : null}
        </div>
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
        <PipelineRuns key={refreshKey} />
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
