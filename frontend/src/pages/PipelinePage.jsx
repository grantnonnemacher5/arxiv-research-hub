import PipelineRuns from '../components/PipelineRuns.jsx'

export default function PipelinePage({
  refreshKey,
  activePolling,
  cancelRequested,
  pipelineLoading,
  syncInProgress,
  cancelLoading,
  onRunPipeline,
  onCancelPipeline,
}) {
  return (
    <div className="w-full px-6 py-8 pb-16 lg:px-10">
      <header className="mb-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">Pipeline & Operations</h1>
            <p className="mt-1.5 text-sm text-slate-500">Run history, stage metrics, and system status.</p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
            <button
              type="button"
              disabled={pipelineLoading || syncInProgress}
              onClick={onRunPipeline}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-sky-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-700 disabled:opacity-50"
            >
              {pipelineLoading ? (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
              ) : null}
              {pipelineLoading ? 'Starting…' : syncInProgress ? 'Sync running' : 'Run Pipeline'}
            </button>
            {syncInProgress ? (
              <button
                type="button"
                disabled={cancelLoading || cancelRequested}
                onClick={onCancelPipeline}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 shadow-sm hover:bg-slate-50 disabled:opacity-50"
              >
                {cancelLoading || cancelRequested ? 'Stopping…' : 'Stop sync'}
              </button>
            ) : null}
          </div>
        </div>
      </header>
      <PipelineRuns
        refreshKey={refreshKey}
        activePolling={activePolling}
        cancelRequested={cancelRequested}
      />
    </div>
  )
}
