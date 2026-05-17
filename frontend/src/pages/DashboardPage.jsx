import { useEffect, useMemo, useState } from 'react'
import {
  getPapers,
  getPapersOverTime,
  getPipelineRuns,
  listReports,
} from '../api'
import AreaChart from '../components/charts/AreaChart.jsx'
import DonutChart from '../components/charts/DonutChart.jsx'
import CategoryBadge from '../components/CategoryBadge.jsx'
import { DONUT_COLORS, RESEARCH_BUCKETS } from '../constants/buckets.js'
import { fillDailySeries } from '../lib/chartData.js'
import {
  computePipelineSuccess,
  formatDurationMs,
  PIPELINE_SUCCESS_HINT,
  pipelineStatusLabel,
} from '../lib/pipelineMetrics.js'

/** Shared dashboard card — generous padding and soft border so grids don’t feel cramped. */
const DASH_CARD =
  'rounded-2xl border border-slate-200/60 bg-white p-5 shadow-[0_1px_3px_rgba(15,23,42,0.06)] sm:p-6'

function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

function KpiInfo({ hint }) {
  if (!hint) return null
  return (
    <span
      className="inline-flex h-4 w-4 shrink-0 cursor-help items-center justify-center rounded-full text-[10px] font-bold leading-none text-slate-400 ring-1 ring-slate-200/80 hover:bg-slate-50 hover:text-slate-600"
      title={hint}
      aria-label={hint}
      role="img"
    >
      i
    </span>
  )
}

function KpiCard({ label, value, sub, detail, hint, icon, iconClass }) {
  return (
    <div className={DASH_CARD}>
      <div className="flex items-start gap-3">
        <span
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-base ${iconClass}`}
          aria-hidden
        >
          {icon}
        </span>
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <p className="text-xs font-medium text-slate-500">{label}</p>
            <KpiInfo hint={hint} />
          </div>
          <p className="mt-0.5 text-2xl font-bold tabular-nums tracking-tight text-slate-900">{value}</p>
          {sub ? <p className="mt-0.5 text-[11px] leading-snug text-slate-400">{sub}</p> : null}
          {detail ? <p className="mt-1 text-[10px] leading-snug text-slate-400">{detail}</p> : null}
        </div>
      </div>
    </div>
  )
}

export default function DashboardPage({ stats, statsLoading = false, refreshKey, onNavigate }) {
  const [reportsCount, setReportsCount] = useState(null)
  const [pipelineRuns, setPipelineRuns] = useState([])
  const [recentPapers, setRecentPapers] = useState([])
  const [timeSeries, setTimeSeries] = useState([])
  const [loadingExtra, setLoadingExtra] = useState(true)

  const totalPapers = stats?.total_papers ?? 0
  const buckets = stats?.buckets ?? {}

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoadingExtra(true)
      try {
        const [reports, runs, papers, overTime] = await Promise.all([
          listReports(),
          getPipelineRuns({ page: 1, pageSize: 30 }),
          getPapers({ page: 1, pageSize: 6 }),
          getPapersOverTime(90),
        ])
        if (cancelled) return
        setReportsCount(Array.isArray(reports) ? reports.length : 0)
        setPipelineRuns(runs?.items ?? [])
        setRecentPapers(papers?.items ?? [])
        setTimeSeries(fillDailySeries(overTime?.points, overTime?.days ?? 90))
      } catch {
        if (!cancelled) {
          setReportsCount(null)
          setPipelineRuns([])
          setRecentPapers([])
          setTimeSeries([])
        }
      } finally {
        if (!cancelled) setLoadingExtra(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [refreshKey])

  const pipelineSuccess = useMemo(() => computePipelineSuccess(pipelineRuns), [pipelineRuns])
  const recentRuns = pipelineRuns.slice(0, 5)

  const donutSegments = RESEARCH_BUCKETS.map((b, i) => ({
    label: b.label,
    value: buckets[b.key] ?? 0,
    color: DONUT_COLORS[i],
  }))
  const bucketTotal = donutSegments.reduce((a, s) => a + s.value, 0)

  return (
    <div className="w-full px-6 py-8 pb-16 lg:px-10">
      <header className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Dashboard</h1>
        <p className="mt-1.5 text-sm text-slate-500">Real-time overview of your Research hub pipeline.</p>
      </header>

      <div className="flex flex-col gap-8 lg:gap-10">
      <div className="grid gap-5 sm:grid-cols-2 sm:gap-6 xl:grid-cols-4">
        <KpiCard
          label="Total Papers"
          value={statsLoading && stats == null ? '…' : (stats?.total_papers ?? '—')}
          sub="across 3 research buckets"
          icon="📚"
          iconClass="bg-sky-100 text-sky-600"
        />
        <KpiCard
          label="Today"
          value={statsLoading && stats == null ? '…' : (stats?.papers_today ?? '—')}
          sub="ingested today"
          icon="⚡"
          iconClass="bg-emerald-100 text-emerald-600"
        />
        <KpiCard
          label="Reports"
          value={loadingExtra ? '—' : (reportsCount ?? '—')}
          sub="generated HTML reports"
          icon="📄"
          iconClass="bg-sky-100 text-sky-600"
        />
        <KpiCard
          label="Pipeline Success"
          value={pipelineSuccess.pct != null ? `${pipelineSuccess.pct}%` : loadingExtra ? '—' : '—'}
          sub={
            pipelineSuccess.total > 0
              ? `${pipelineSuccess.completed}/${pipelineSuccess.total} finished runs`
              : 'last 30 ingest runs'
          }
          detail="Completed only · stopped & failed lower rate"
          hint={PIPELINE_SUCCESS_HINT}
          icon="💜"
          iconClass="bg-rose-100 text-rose-600"
        />
      </div>

      <div className="grid gap-5 sm:gap-6 lg:grid-cols-5">
        <section className={`${DASH_CARD} lg:col-span-3`}>
          <h2 className="text-sm font-semibold text-slate-900">Papers published over time</h2>
          <p className="mt-1 text-xs text-slate-500">Last 90 days (published or ingested date)</p>
          <div className="mt-5">
            {loadingExtra ? (
              <div className="flex h-[200px] items-center justify-center text-sm text-slate-400">Loading chart…</div>
            ) : (
              <AreaChart series={timeSeries} height={200} />
            )}
          </div>
        </section>

        <section className={`${DASH_CARD} lg:col-span-2`}>
          <h2 className="text-sm font-semibold text-slate-900">Bucket distribution</h2>
          <p className="mt-1 text-xs text-slate-500">
            Legend counts are per bucket; center shows total unique papers.
          </p>
          <div className="mt-6 flex flex-col items-center gap-6 sm:flex-row sm:justify-center sm:gap-8">
            <DonutChart segments={donutSegments} size={160} centerValue={totalPapers} />
            <ul className="min-w-[140px] space-y-2.5 text-sm">
              {donutSegments.map((seg) => {
                const pct = bucketTotal > 0 ? Math.round((100 * seg.value) / bucketTotal) : 0
                return (
                  <li key={seg.label} className="flex items-center gap-2">
                    <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: seg.color }} />
                    <span className="text-slate-600">{seg.label}</span>
                    <span className="ml-auto tabular-nums text-slate-900">
                      <span className="font-semibold">{seg.value}</span>
                      <span className="text-slate-400"> ({pct}%)</span>
                    </span>
                  </li>
                )
              })}
            </ul>
          </div>
        </section>
      </div>

      <div className="grid gap-5 sm:gap-6 lg:grid-cols-2">
        <section className={DASH_CARD}>
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-slate-900">Recent papers</h2>
            <button
              type="button"
              onClick={() => onNavigate?.('papers')}
              className="text-xs font-semibold text-sky-700 hover:text-sky-900"
            >
              View all →
            </button>
          </div>
          {loadingExtra ? (
            <p className="mt-4 text-sm text-slate-400">Loading…</p>
          ) : recentPapers.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">No papers yet — run a sync from Pipeline.</p>
          ) : (
            <ul className="mt-4 divide-y divide-slate-100">
              {recentPapers.map((p) => (
                <li key={p.id} className="py-3 first:pt-0">
                  <p className="line-clamp-1 text-sm font-medium text-sky-800">{p.title}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <span className="text-xs text-slate-500">{formatDate(p.published_date)}</span>
                    {(p.buckets || '')
                      .split(',')
                      .map((s) => s.trim())
                      .filter(Boolean)
                      .slice(0, 2)
                      .map((label) => (
                        <CategoryBadge key={label} label={label} />
                      ))}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className={DASH_CARD}>
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-slate-900">Pipeline runs</h2>
            <button
              type="button"
              onClick={() => onNavigate?.('pipeline')}
              className="text-xs font-semibold text-sky-700 hover:text-sky-900"
            >
              View all →
            </button>
          </div>
          {loadingExtra ? (
            <p className="mt-4 text-sm text-slate-400">Loading…</p>
          ) : recentRuns.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">No runs recorded yet.</p>
          ) : (
            <ul className="mt-4 space-y-2">
              {recentRuns.map((r) => (
                <li
                  key={r.id}
                  className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 bg-slate-50/80 px-3 py-2.5"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium capitalize text-slate-800">{r.trigger} ingest</p>
                    <p className="text-xs text-slate-500">
                      {formatDurationMs(r.duration_ms)}
                      {r.saved != null ? ` · ${r.saved} saved` : ''}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 rounded-md px-2 py-0.5 text-xs font-medium ${
                      r.status === 'completed'
                        ? 'bg-emerald-100 text-emerald-900'
                        : r.status === 'running'
                          ? 'bg-amber-100 text-amber-950'
                          : r.status === 'cancelled'
                            ? 'bg-slate-200 text-slate-800'
                            : 'bg-red-100 text-red-900'
                    }`}
                  >
                    {pipelineStatusLabel(r.status)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
      </div>
    </div>
  )
}
