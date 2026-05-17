import { useEffect, useRef, useState } from "react";
import { getPipelineRuns } from "../api";
import { friendlyErrorMessage } from "../lib/apiErrors.js";

const PAGE_SIZE = 10;
const ACTIVE_POLL_MS = 2500;
const IDLE_POLL_MS = 30000;

/**
 * Self-polling table. While the latest run is ``running`` *or* the parent says
 * a sync is in progress (so we keep polling fast right after Sync is pressed
 * before the row exists yet) we refresh every ACTIVE_POLL_MS; otherwise we
 * slow down to IDLE_POLL_MS. The component never re-shows the initial
 * "Loading runs…" spinner after the first successful fetch — background
 * refreshes update rows in place so the table never disappears or flickers.
 *
 * ``refreshKey`` is optional: bumping it forces an immediate refetch (used by
 * the dashboard right after Sync / Stop click), but is not required.
 * ``activePolling`` lets the dashboard say "I just kicked off a run, please
 * keep polling fast even if no running row is visible yet".
 * ``cancelRequested`` paints the running row's status badge as "Stopping…".
 */
export default function PipelineRuns({
  refreshKey = 0,
  activePolling = false,
  cancelRequested = false,
}) {
  const [page, setPage] = useState(1);
  const [payload, setPayload] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(true);
  const firstLoadDoneRef = useRef(false);
  const timerRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    const fetchOnce = async () => {
      if (!firstLoadDoneRef.current) {
        setLoading(true);
      }
      try {
        const data = await getPipelineRuns({ page, pageSize: PAGE_SIZE });
        if (cancelled) return null;
        setErr(null);
        setPayload(data);
        firstLoadDoneRef.current = true;
        return data;
      } catch (e) {
        if (cancelled) return null;
        if (!firstLoadDoneRef.current) {
          setErr(friendlyErrorMessage(e?.message || e));
        }
        return null;
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    const schedule = (data) => {
      if (cancelled) return;
      const hasRunning = (data?.items ?? []).some((r) => r.status === "running");
      const next = hasRunning || activePolling ? ACTIVE_POLL_MS : IDLE_POLL_MS;
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(async () => {
        const d = await fetchOnce();
        schedule(d ?? payload);
      }, next);
    };

    (async () => {
      const data = await fetchOnce();
      schedule(data);
    })();

    return () => {
      cancelled = true;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
    // We intentionally exclude `payload` — we only use it as a fallback inside
    // the scheduler; including it would cancel + restart polling on every fetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, refreshKey, activePolling]);

  const total = payload?.total ?? 0;
  const items = payload?.items ?? [];
  const totalPages = !payload?.page_size
    ? 1
    : Math.max(1, Math.ceil(total / payload.page_size));

  return (
    <section className="rounded-2xl border border-slate-200/60 bg-white p-5 shadow-[0_1px_3px_rgba(15,23,42,0.06)] sm:p-6">
      <h2 className="text-sm font-semibold text-slate-900">Pipeline runs</h2>
      <details className="group mt-3 rounded-xl border border-slate-100 bg-slate-50/80">
        <summary className="cursor-pointer list-none px-4 py-2.5 text-sm font-medium text-slate-700 marker:content-none [&::-webkit-details-marker]:hidden">
          <span className="inline-flex items-center gap-2">
            <span className="text-slate-400 transition group-open:rotate-90">▸</span>
            How to read this table
          </span>
        </summary>
        <ul className="space-y-1.5 border-t border-slate-100 px-4 py-3 text-sm leading-relaxed text-slate-600">
          <li>
            <strong className="font-medium text-slate-700">Saved</strong> — new papers ingested this run.
          </li>
          <li>
            <strong className="font-medium text-slate-700">Skipped</strong> — arXiv id was already in your library.
          </li>
          <li>
            <strong className="font-medium text-slate-700">Completed</strong> with 0 saved usually means the batch was all duplicates, not a failed sync.
          </li>
          <li>
            <strong className="font-medium text-slate-700">Running</strong> — saved/skipped update in batches while the job is active.
          </li>
          <li>
            <strong className="font-medium text-slate-700">Stopped</strong> — you cancelled from Pipeline; a crash may leave a row as running until the next deploy.
          </li>
        </ul>
      </details>
      {err && !firstLoadDoneRef.current && (
        <p className="mt-3 text-sm text-red-700" role="alert">
          {err}
        </p>
      )}
      {loading && !firstLoadDoneRef.current && (
        <p className="mt-4 flex items-center gap-2 text-sm text-slate-500">
          <span
            className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-sky-500"
            aria-hidden
          />
          Loading runs…
        </p>
      )}

      {firstLoadDoneRef.current && total === 0 && (
        <p className="mt-4 text-sm text-slate-500">
          No runs recorded yet. Run &quot;Sync arXiv&quot; once.
        </p>
      )}

      {firstLoadDoneRef.current && items.length > 0 && (
        <div className="mt-5 overflow-hidden rounded-lg border border-slate-200">
          <div className="overflow-x-auto">
          <table className="w-full min-w-[880px] table-fixed border-collapse text-left text-sm">
            <thead>
              <tr className="border-b-2 border-slate-200 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-600">
                <th
                  className="w-[17%] px-4 py-3"
                  title="US Central (Chicago). Daylight saving: CDT. Standard time: CST."
                >
                  Finished (CT)
                </th>
                <th className="w-[9%] px-4 py-3">Trigger</th>
                <th className="w-[11%] px-4 py-3">Status</th>
                <th className="w-[8%] px-4 py-3 text-right">Saved</th>
                <th className="w-[8%] px-4 py-3 text-right">Skipped</th>
                <th className="w-[9%] px-4 py-3 text-right">Backfill</th>
                <th className="w-[10%] px-4 py-3 text-right">Duration</th>
                <th className="px-4 py-3">Error</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr
                  key={r.id}
                  className="border-b border-slate-200 bg-white"
                >
                  <td
                    className="px-4 py-3 font-mono text-xs text-slate-700"
                    title={
                      r.finished_at
                        ? `${r.finished_at} (UTC) · US Central, America/Chicago (CST or CDT by date)`
                        : ""
                    }
                  >
                    {r.finished_at ? formatFinishedChicago(r.finished_at) : "—"}
                  </td>
                  <td className="px-4 py-3 capitalize text-slate-700">{r.trigger}</td>
                  <td className="px-4 py-3">
                    <span
                      className={
                        r.status === "completed"
                          ? "rounded-md bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-900"
                          : r.status === "running"
                            ? "rounded-md bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-950"
                            : r.status === "cancelled"
                              ? "rounded-md bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-800"
                              : "rounded-md bg-red-100 px-2 py-0.5 text-xs font-medium text-red-900"
                      }
                    >
                      {r.status === "running" && cancelRequested
                        ? "Stopping…"
                        : pipelineStatusLabel(r.status)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-800">{r.saved}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-800">
                    {r.skipped_duplicates}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-800">{r.backfilled}</td>
                  <td
                    className="px-4 py-3 text-right text-slate-700"
                    title={
                      r.duration_ms != null
                        ? `${r.duration_ms.toLocaleString()} ms`
                        : ""
                    }
                  >
                    {formatDurationMs(r.duration_ms)}
                  </td>
                  <td
                    className={`truncate px-4 py-3 text-xs ${
                      r.status === "failed"
                        ? "text-red-800"
                        : r.status === "cancelled"
                          ? "text-slate-700"
                          : "text-slate-600"
                    }`}
                    title={r.error || ""}
                  >
                    {r.error || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600">
              <p className="tabular-nums">
                Page{" "}
                <span className="font-semibold text-slate-800">{page}</span> of{" "}
                <span className="font-semibold text-slate-800">
                  {totalPages}
                </span>
                <span className="mx-2 text-slate-300">·</span>
                {total} run{total !== 1 ? "s" : ""} total
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
        </div>
      )}
    </section>
  );
}

/** DB uses `cancelled`; UI shows “Stopped” for Grant-facing copy. */
function pipelineStatusLabel(status) {
  switch (status) {
    case "completed":
      return "Completed";
    case "running":
      return "Running";
    case "failed":
      return "Failed";
    case "cancelled":
      return "Stopped";
    default:
      return status || "—";
  }
}
/** US Central wall clock: America/Chicago (CST in winter, CDT in summer). */
function formatFinishedChicago(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleString("en-US", {
      timeZone: "America/Chicago",
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
      timeZoneName: "short",
    });
  } catch {
    return iso;
  }
}

/** Human-readable run length; hover shows exact ms for ops. */
function formatDurationMs(ms) {
  if (ms == null || Number.isNaN(ms) || ms < 0) return "—";
  const n = Math.floor(Number(ms));
  if (n < 1000) return `${n} ms`;
  const sec = Math.floor(n / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const s = sec % 60;
  if (min < 60) return `${min}m ${s}s`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return `${h}h ${m}m`;
}
