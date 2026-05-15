import { useEffect, useState } from "react";
import { getPipelineRuns } from "../api";
import { friendlyErrorMessage } from "../lib/apiErrors.js";

const PAGE_SIZE = 10;

export default function PipelineRuns() {
  const [page, setPage] = useState(1);
  const [payload, setPayload] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setErr(null);
      setLoading(true);
      try {
        const data = await getPipelineRuns({ page, pageSize: PAGE_SIZE });
        if (!cancelled) setPayload(data);
      } catch (e) {
        if (!cancelled) {
          setErr(friendlyErrorMessage(e?.message || e));
          setPayload(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [page]);

  const total = payload?.total ?? 0;
  const items = payload?.items ?? [];
  const totalPages = !payload?.page_size
    ? 1
    : Math.max(1, Math.ceil(total / payload.page_size));

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <h2 className="font-serif text-lg font-semibold text-slate-900">
        Pipeline runs
      </h2>
      <p className="mt-1 text-sm text-slate-500">
        Recent sync jobs —{" "}
        <strong className="font-medium text-slate-600">Saved</strong> is new
        papers;
        <strong className="font-medium text-slate-600"> skipped</strong> means
        that arXiv id was already in your library. Completed + 0 saved usually
        means the fetched batch was all duplicates, not a failed sync.{" "}
        <strong className="font-medium text-slate-600">Running</strong> updates
        saved/skipped in batches while the job is active.{" "}
        <strong className="font-medium text-slate-600">Stopped</strong> means you cancelled the sync
        from the dashboard; if the server crashes first, the row may stay running until the next
        deploy (then it is marked failed). Dashboard totals always come
        from the papers table.
      </p>
      {err && (
        <p className="mt-3 text-sm text-red-700" role="alert">
          {err}
        </p>
      )}
      {loading && !err && (
        <p className="mt-4 flex items-center gap-2 text-sm text-slate-500">
          <span
            className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-sky-500"
            aria-hidden
          />
          Loading runs…
        </p>
      )}

      {!loading && !err && total === 0 && (
        <p className="mt-4 text-sm text-slate-500">
          No runs recorded yet. Run &quot;Sync arXiv&quot; once.
        </p>
      )}

      {!loading && !err && items.length > 0 && (
        <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200">
          <table className="w-full min-w-[720px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-600">
                <th
                  className="border-r border-slate-200 px-3 py-2.5"
                  title="US Central (Chicago). Daylight saving: CDT. Standard time: CST."
                >
                  Finished (CT)
                </th>
                <th className="border-r border-slate-200 px-3 py-2.5">
                  Trigger
                </th>
                <th className="border-r border-slate-200 px-3 py-2.5">
                  Status
                </th>
                <th className="border-r border-slate-200 px-3 py-2.5 text-right">
                  Saved
                </th>
                <th className="border-r border-slate-200 px-3 py-2.5 text-right">
                  Skipped
                </th>
                <th className="border-r border-slate-200 px-3 py-2.5 text-right">
                  Backfill
                </th>
                <th className="border-r border-slate-200 px-3 py-2.5 text-right">
                  Duration
                </th>
                <th className="px-3 py-2.5">Error</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr
                  key={r.id}
                  className="border-b border-slate-100 odd:bg-white even:bg-slate-50/60 last:border-b-0"
                >
                  <td
                    className="border-r border-slate-200 px-3 py-2.5 font-mono text-xs text-slate-700"
                    title={
                      r.finished_at
                        ? `${r.finished_at} (UTC) · US Central, America/Chicago (CST or CDT by date)`
                        : ""
                    }
                  >
                    {r.finished_at ? formatFinishedChicago(r.finished_at) : "—"}
                  </td>
                  <td className="border-r border-slate-200 px-3 py-2.5 text-slate-700">
                    {r.trigger}
                  </td>
                  <td className="border-r border-slate-200 px-3 py-2.5">
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
                      {pipelineStatusLabel(r.status)}
                    </span>
                  </td>
                  <td className="border-r border-slate-200 px-3 py-2.5 text-right tabular-nums text-slate-800">
                    {r.saved}
                  </td>
                  <td className="border-r border-slate-200 px-3 py-2.5 text-right tabular-nums text-slate-800">
                    {r.skipped_duplicates}
                  </td>
                  <td className="border-r border-slate-200 px-3 py-2.5 text-right tabular-nums text-slate-800">
                    {r.backfilled}
                  </td>
                  <td
                    className="border-r border-slate-200 px-3 py-2.5 text-right text-slate-700"
                    title={
                      r.duration_ms != null
                        ? `${r.duration_ms.toLocaleString()} ms`
                        : ""
                    }
                  >
                    <span className="tabular-nums">
                      {formatDurationMs(r.duration_ms)}
                    </span>
                  </td>
                  <td
                    className={`max-w-[220px] truncate px-3 py-2.5 text-xs ${
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
          {totalPages > 1 ? (
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 bg-slate-50/50 px-3 py-2.5 text-xs text-slate-600">
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
          ) : null}
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
