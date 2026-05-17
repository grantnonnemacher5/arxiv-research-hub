import { useState } from 'react'
import { apiUrl, generateReport } from '../api'
import { friendlyErrorMessage } from '../lib/apiErrors.js'

const PERIODS = [
  { id: '7d', title: 'Last 7 Days', subtitle: 'Weekly digest', icon: '📅', iconClass: 'bg-sky-100 text-sky-700' },
  { id: '1m', title: 'Last Month', subtitle: '~30 day window', icon: '📆', iconClass: 'bg-emerald-100 text-emerald-700' },
  { id: '3m', title: 'Last 3 Months', subtitle: 'Quarterly view', icon: '📊', iconClass: 'bg-amber-100 text-amber-800' },
  { id: '6m', title: 'Last 6 Months', subtitle: 'Half-year scan', icon: '📈', iconClass: 'bg-rose-100 text-rose-700' },
  { id: '1y', title: 'Last Year', subtitle: 'Annual landscape', icon: '🗓️', iconClass: 'bg-blue-100 text-blue-700' },
]

function Spinner({ className = '' }) {
  return (
    <span
      className={`inline-block h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent ${className}`}
      aria-hidden
    />
  )
}

export default function ReportButtons({ onToast, onReportDone }) {
  const [loading, setLoading] = useState(null)

  async function handle(period) {
    setLoading(period)
    onToast(null)
    try {
      const data = await generateReport(period)
      const href = apiUrl(data.url)
      window.open(href, '_blank', 'noopener,noreferrer')
      onReportDone?.()
      onToast({ type: 'ok', text: `Opened report: ${data.filename}` })
    } catch (e) {
      onToast({ type: 'err', text: friendlyErrorMessage(e?.message || e) })
    } finally {
      setLoading(null)
    }
  }

  return (
    <div
      className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 sm:gap-3 md:grid-cols-3 lg:grid-cols-5"
      role="group"
      aria-label="Generate report by time window"
    >
      {PERIODS.map(({ id, title, subtitle, icon, iconClass }) => {
        const busy = loading === id
        const waiting = loading !== null && !busy
        return (
          <button
            key={id}
            type="button"
            disabled={waiting}
            aria-busy={busy}
            onClick={() => handle(id)}
            className={`flex flex-col rounded-xl border border-slate-200/80 bg-white p-3.5 text-left shadow-[0_1px_3px_rgba(15,23,42,0.06)] transition hover:border-sky-200 hover:shadow-md disabled:cursor-not-allowed disabled:opacity-60 sm:p-4 ${
              busy ? 'border-sky-300 ring-2 ring-sky-100' : ''
            }`}
          >
            <span
              className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-base sm:h-10 sm:w-10 sm:text-lg ${iconClass}`}
              aria-hidden
            >
              {busy ? <Spinner /> : icon}
            </span>
            <span className="mt-2.5 text-sm font-semibold leading-snug text-slate-900">{title}</span>
            <span className="mt-0.5 text-xs leading-snug text-slate-500">{subtitle}</span>
          </button>
        )
      })}
    </div>
  )
}
