import { useCallback, useEffect, useState } from 'react'
import AppShell from './components/shell/AppShell.jsx'
import { getStats } from './api'
import { friendlyErrorMessage } from './lib/apiErrors.js'
import { usePipelineSync } from './hooks/usePipelineSync.js'
import DashboardPage from './pages/DashboardPage.jsx'
import PapersPage from './pages/PapersPage.jsx'
import PipelinePage from './pages/PipelinePage.jsx'
import ReportsPage from './pages/ReportsPage.jsx'

export default function App() {
  const [page, setPage] = useState('dashboard')
  const [stats, setStats] = useState(null)
  const [statsLoading, setStatsLoading] = useState(true)
  const [refreshKey, setRefreshKey] = useState(0)
  const [pageToast, setPageToast] = useState(null)

  const refreshStats = useCallback(async () => {
    setStatsLoading(true)
    try {
      const s = await getStats()
      setStats(s)
    } catch (e) {
      setPageToast({ type: 'err', text: friendlyErrorMessage(e) })
    } finally {
      setStatsLoading(false)
    }
  }, [])

  const bumpRefresh = useCallback(() => {
    setRefreshKey((k) => k + 1)
  }, [])

  const pipeline = usePipelineSync({
    refreshStats,
    onSyncEnd: bumpRefresh,
  })

  useEffect(() => {
    void refreshStats()
  }, [refreshStats, refreshKey])

  const displayToast = pipeline.toast || pageToast
  const dismissToast = () => {
    pipeline.setToast(null)
    setPageToast(null)
  }

  const handlePageToast = (t) => {
    setPageToast(t)
    if (t) pipeline.setToast(null)
  }

  const handleReportDone = () => {
    bumpRefresh()
    setPageToast({ type: 'ok', text: 'Report list updated.' })
  }

  const syncBanner =
    pipeline.syncInProgress && page !== 'pipeline' ? (
      <div className="mx-6 mt-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-sky-200 bg-sky-50 px-4 py-2.5 text-sm text-sky-900">
        <span>Sync in progress — stats update automatically.</span>
        <button
          type="button"
          onClick={() => setPage('pipeline')}
          className="font-semibold text-sky-800 underline-offset-2 hover:underline"
        >
          Open Pipeline
        </button>
      </div>
    ) : null

  let content
  if (page === 'dashboard') {
    content = (
      <DashboardPage
        stats={stats}
        statsLoading={statsLoading}
        refreshKey={refreshKey}
        onNavigate={setPage}
      />
    )
  } else if (page === 'papers') {
    content = <PapersPage refreshKey={refreshKey} onToast={handlePageToast} />
  } else if (page === 'pipeline') {
    content = (
      <PipelinePage
        refreshKey={refreshKey}
        activePolling={pipeline.syncInProgress}
        cancelRequested={pipeline.cancelRequested}
        pipelineLoading={pipeline.pipelineLoading}
        syncInProgress={pipeline.syncInProgress}
        cancelLoading={pipeline.cancelLoading}
        onRunPipeline={pipeline.handleRunPipeline}
        onCancelPipeline={pipeline.handleCancelPipeline}
      />
    )
  } else if (page === 'reports') {
    content = (
      <ReportsPage refreshKey={refreshKey} onToast={handlePageToast} onReportDone={handleReportDone} />
    )
  } else {
    content = (
      <DashboardPage
        stats={stats}
        statsLoading={statsLoading}
        refreshKey={refreshKey}
        onNavigate={setPage}
      />
    )
  }

  return (
    <AppShell
      activePage={page}
      onNavigate={setPage}
      paperCount={stats?.total_papers}
      syncBanner={syncBanner}
      toast={displayToast}
      onDismissToast={dismissToast}
    >
      {content}
    </AppShell>
  )
}
