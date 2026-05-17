import ReportButtons from '../components/ReportButtons.jsx'
import ReportViewer from '../components/ReportViewer.jsx'
import { PAGE_SHELL } from '../constants/layout.js'

const SECTION_LABEL = 'text-xs font-semibold uppercase tracking-wider text-slate-500'

export default function ReportsPage({ refreshKey, onToast, onReportDone }) {
  return (
    <div className={PAGE_SHELL}>
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Research Reports</h1>
        <p className="mt-1 max-w-2xl text-sm leading-relaxed text-slate-500">
          Generate LLM-powered digests grouped by research bucket with cross-domain synthesis.
        </p>
      </header>

      <div className="flex flex-col gap-6 lg:gap-8">
        <section className="space-y-3">
          <h2 className={SECTION_LABEL}>Generate new report</h2>
          <ReportButtons onToast={onToast} onReportDone={onReportDone} />
        </section>

        <section className="space-y-3">
          <h2 className={SECTION_LABEL}>Report history</h2>
          <ReportViewer refreshKey={refreshKey} onToast={onToast} />
        </section>
      </div>
    </div>
  )
}
