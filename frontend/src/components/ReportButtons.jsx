import { useState } from 'react'
import { apiUrl, generateReport } from '../api'
import { friendlyErrorMessage } from '../lib/apiErrors.js'

const PERIODS = [
  { id: '7d', label: '7d' },
  { id: '1m', label: '1m' },
  { id: '3m', label: '3m' },
  { id: '6m', label: '6m' },
  { id: '1y', label: '1y' },
]

function Spinner({ className = '' }) {
  return (
    <span
      className={`inline-block h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent opacity-90 ${className}`}
      aria-hidden
    />
  )
}

export default function ReportButtons({ onToast, onReportDone }) {
  const [loading, setLoading] = useState(null)
  const [activePeriod, setActivePeriod] = useState('7d')

  async function handle(period) {
    setActivePeriod(period)
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
      className="grid w-full grid-cols-2 gap-2 sm:grid-cols-5"
      role="group"
      aria-label="Report window length"
    >
      {PERIODS.map(({ id, label }) => {
        const busy = loading === id
        const waiting = loading !== null && !busy
        const selected = activePeriod === id
        return (
          <button
            key={id}
            type="button"
            disabled={waiting}
            aria-pressed={selected}
            aria-busy={busy}
            title={`Generate report: ${label}`}
            onClick={() => handle(id)}
            className={`flex min-w-0 items-center justify-center gap-1.5 rounded-lg border-2 px-2 py-2 text-sm font-semibold tabular-nums shadow-sm transition ${
              busy
                ? 'cursor-wait border-sky-600 bg-sky-500 text-white hover:bg-sky-600'
                : selected
                  ? 'border-sky-600 bg-sky-500 text-white hover:bg-sky-600 disabled:opacity-50'
                  : 'border-slate-300 bg-slate-50 text-slate-800 hover:border-slate-400 hover:bg-slate-100 disabled:opacity-50'
            }`}
          >
            {busy ? <Spinner className="border-white border-t-transparent" /> : null}
            <span>{label}</span>
          </button>
        )
      })}
    </div>
  )
}
