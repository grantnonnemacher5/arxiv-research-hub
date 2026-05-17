import { useCallback, useEffect, useRef, useState } from 'react'
import { cancelPipeline, getPipelineBusy, getPipelineRuns, runPipeline } from '../api'
import { friendlyErrorMessage } from '../lib/apiErrors.js'

/**
 * Global pipeline sync state — run/stop, watch `/pipeline-status`, refresh stats on end.
 * Pass `onSyncEnd` to bump refreshKey / refetch lists; `refreshStats` while sync runs.
 */
export function usePipelineSync({ refreshStats, onSyncEnd } = {}) {
  const [pipelineLoading, setPipelineLoading] = useState(false)
  const [syncInProgress, setSyncInProgress] = useState(false)
  const [cancelLoading, setCancelLoading] = useState(false)
  const [cancelRequested, setCancelRequested] = useState(false)
  const [toast, setToast] = useState(null)

  const pipelinePollRef = useRef(null)
  const pipelineEverSawActiveRef = useRef(false)
  const pipelineIdleStreakRef = useRef(0)
  const pipelineWatchStartedAtRef = useRef(0)
  const pipelineStatsTickRef = useRef(0)

  const refreshStatsRef = useRef(refreshStats)
  const onSyncEndRef = useRef(onSyncEnd)
  useEffect(() => {
    refreshStatsRef.current = refreshStats
    onSyncEndRef.current = onSyncEnd
  }, [refreshStats, onSyncEnd])

  const stopPipelineSyncWatch = useCallback(() => {
    if (pipelinePollRef.current) {
      clearInterval(pipelinePollRef.current)
      pipelinePollRef.current = null
    }
  }, [])

  const startPipelineSyncWatch = useCallback(() => {
    stopPipelineSyncWatch()
    pipelineEverSawActiveRef.current = false
    pipelineIdleStreakRef.current = 0
    pipelineStatsTickRef.current = 0
    pipelineWatchStartedAtRef.current = Date.now()

    const pollMs = 2500
    const statsRefreshEveryTicks = 3

    const tick = async () => {
      try {
        let busy = false
        try {
          const b = await getPipelineBusy()
          busy = !!b?.busy
        } catch {
          return
        }

        if (busy) {
          pipelineEverSawActiveRef.current = true
          pipelineIdleStreakRef.current = 0
          pipelineStatsTickRef.current += 1
          if (pipelineStatsTickRef.current % statsRefreshEveryTicks === 0) {
            void refreshStatsRef.current?.()
          }
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
        setCancelRequested(false)
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
        await refreshStatsRef.current?.()
        onSyncEndRef.current?.()
      } catch {
        /* keep watch alive */
      }
    }

    void tick()
    pipelinePollRef.current = setInterval(tick, pollMs)
  }, [stopPipelineSyncWatch])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const b = await getPipelineBusy()
        if (cancelled) return
        if (b?.busy) {
          setSyncInProgress(true)
          startPipelineSyncWatch()
        }
      } catch {
        /* ignore */
      }
    })()
    return () => {
      cancelled = true
      stopPipelineSyncWatch()
    }
  }, [startPipelineSyncWatch, stopPipelineSyncWatch])

  const handleCancelPipeline = useCallback(async () => {
    setCancelLoading(true)
    setToast(null)
    try {
      await cancelPipeline()
      setCancelRequested(true)
      setToast({
        type: 'ok',
        text: 'Stop requested — ingest stops after the current paper (if any).',
      })
    } catch (e) {
      setToast({ type: 'err', text: friendlyErrorMessage(e?.message || e) })
    } finally {
      setCancelLoading(false)
    }
  }, [])

  const handleRunPipeline = useCallback(async () => {
    setPipelineLoading(true)
    setToast(null)
    try {
      const res = await runPipeline()
      if (res.status === 'accepted') {
        stopPipelineSyncWatch()
        setCancelRequested(false)
        setSyncInProgress(true)
        startPipelineSyncWatch()
        void refreshStatsRef.current?.()
        setToast({
          type: 'ok',
          text:
            res.message ||
            'Sync started on the server. Use Stop sync to cancel; stats update while the job runs.',
        })
        onSyncEndRef.current?.()
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
      onSyncEndRef.current?.()
    } catch (e) {
      setToast({ type: 'err', text: friendlyErrorMessage(e?.message || e) })
    } finally {
      setPipelineLoading(false)
    }
  }, [startPipelineSyncWatch, stopPipelineSyncWatch])

  return {
    pipelineLoading,
    syncInProgress,
    cancelLoading,
    cancelRequested,
    toast,
    setToast,
    handleRunPipeline,
    handleCancelPipeline,
  }
}
