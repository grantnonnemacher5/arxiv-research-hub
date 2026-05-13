import { useState } from 'react'
import { searchCorpus } from '../api'
import { friendlyErrorMessage } from '../lib/apiErrors.js'
import CategoryBadge from './CategoryBadge.jsx'

const MODES = [
  { value: 'hybrid', label: 'Hybrid (keyword + semantic)' },
  { value: 'keyword', label: 'Keyword only' },
  { value: 'semantic', label: 'Semantic only' },
]

const BUCKETS = [
  { value: '', label: 'All buckets' },
  { value: 'General AI', label: 'General AI' },
  { value: 'Autonomous Agents', label: 'Agents' },
  { value: 'AI x Finance', label: 'Finance' },
]

function arxivAbsUrl(arxivId) {
  if (!arxivId) return null
  return `https://arxiv.org/abs/${encodeURIComponent(String(arxivId).trim())}`
}

export default function PaperSearch() {
  const [q, setQ] = useState('')
  const [mode, setMode] = useState('hybrid')
  const [bucket, setBucket] = useState('')
  const [rerank, setRerank] = useState(false)
  const [loading, setLoading] = useState(false)
  const [payload, setPayload] = useState(null)
  const [err, setErr] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    const needle = q.trim()
    if (!needle) {
      setErr('Enter a search query.')
      return
    }
    setLoading(true)
    setErr(null)
    setPayload(null)
    try {
      const data = await searchCorpus({
        q: needle,
        mode,
        bucket: bucket || undefined,
        limit: 20,
        rerank: mode === 'hybrid' && rerank,
      })
      setPayload(data)
    } catch (e) {
      setErr(friendlyErrorMessage(e?.message || e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <h2 className="font-serif text-lg font-semibold text-slate-900">Search corpus</h2>

      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
        <label className="block min-w-[min(100%,220px)] flex-1">
          <span className="text-xs font-medium text-slate-600">Query</span>
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="e.g. reinforcement learning portfolio risk"
            className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none ring-sky-200 focus:ring-2"
          />
        </label>
        <label className="block w-full min-w-[160px] sm:w-auto">
          <span className="text-xs font-medium text-slate-600">Mode</span>
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none ring-sky-200 focus:ring-2 sm:min-w-[200px]"
          >
            {MODES.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block w-full min-w-[140px] sm:w-auto">
          <span className="text-xs font-medium text-slate-600">Bucket</span>
          <select
            value={bucket}
            onChange={(e) => setBucket(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none ring-sky-200 focus:ring-2"
          >
            {BUCKETS.map((b) => (
              <option key={b.value || 'all'} value={b.value}>
                {b.label}
              </option>
            ))}
          </select>
        </label>
        {mode === 'hybrid' && (
          <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-700 sm:pb-2">
            <input
              type="checkbox"
              checked={rerank}
              onChange={(e) => setRerank(e.target.checked)}
              className="rounded border-slate-300 text-sky-600 focus:ring-sky-500"
            />
            Rerank top results
          </label>
        )}
        <button
          type="submit"
          disabled={loading}
          className="inline-flex h-10 items-center justify-center rounded-lg bg-slate-900 px-5 text-sm font-semibold text-white shadow-sm hover:bg-slate-800 disabled:opacity-50 sm:mb-0.5"
        >
          {loading ? 'Searching…' : 'Search'}
        </button>
      </form>

      {err && (
        <p className="mt-4 text-sm text-red-700" role="alert">
          {err}
        </p>
      )}

      {payload && (
        <div className="mt-6 border-t border-slate-100 pt-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            {payload.items?.length ?? 0} result{(payload.items?.length || 0) !== 1 ? 's' : ''} ·{' '}
            {payload.mode}
            {payload.rerank ? ' · reranked' : ''}
            {payload.dense_ranking && payload.vector_index && payload.vector_index !== 'none'
              ? ` · ${payload.vector_index === 'pgvector_hnsw' ? 'pgvector HNSW' : 'memory scan'}`
              : ''}
          </p>
          {payload.dense_ranking === false &&
          (payload.mode === 'hybrid' || payload.mode === 'semantic') ? (
            <p className="mt-2 rounded border border-amber-100 bg-amber-50 px-2 py-1.5 text-xs text-amber-900">
              Embedding-based ranking is not enabled on this deployment. Showing keyword matches over title and
              abstract only (no OpenAI call).
            </p>
          ) : null}
          {payload.items?.length === 0 ? (
            <p className="mt-3 text-sm text-slate-500">No matches. Try another query or mode.</p>
          ) : (
            <ul className="mt-3 space-y-3">
              {payload.items.map((row) => {
                const abs = arxivAbsUrl(row.paper.arxiv_id)
                const pdf = row.paper.pdf_url?.trim() || null
                return (
                <li
                  key={row.paper.id}
                  className="rounded-lg border border-slate-100 bg-slate-50/80 px-4 py-3 text-sm"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    {abs ? (
                      <a
                        href={abs}
                        target="_blank"
                        rel="noreferrer"
                        className="font-medium text-slate-900 underline decoration-slate-300 decoration-1 underline-offset-2 hover:text-sky-800 hover:decoration-sky-600"
                      >
                        {row.paper.title}
                      </a>
                    ) : (
                      <p className="font-medium text-slate-900">{row.paper.title}</p>
                    )}
                    {abs ? (
                      <a
                        href={abs}
                        target="_blank"
                        rel="noreferrer"
                        className="shrink-0 font-mono text-xs text-sky-700 hover:underline"
                        title="Open on arXiv"
                      >
                        {row.paper.arxiv_id}
                      </a>
                    ) : (
                      <span className="font-mono text-xs text-slate-500">{row.paper.arxiv_id}</span>
                    )}
                  </div>
                  {(pdf || abs) && (
                    <p className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-xs font-medium">
                      {pdf ? (
                        <a
                          href={pdf}
                          target="_blank"
                          rel="noreferrer"
                          className="text-sky-700 hover:underline"
                        >
                          PDF
                        </a>
                      ) : null}
                      {abs ? (
                        <a href={abs} target="_blank" rel="noreferrer" className="text-sky-700 hover:underline">
                          arXiv abstract
                        </a>
                      ) : null}
                    </p>
                  )}
                  <p className="mt-1 text-xs text-slate-600">{row.paper.authors}</p>
                  {row.paper.abstract ? (
                    <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-slate-600">{row.paper.abstract}</p>
                  ) : null}
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    {(row.paper.buckets || '')
                      .split(',')
                      .map((s) => s.trim())
                      .filter(Boolean)
                      .map((label) => (
                        <CategoryBadge key={label} label={label} />
                      ))}
                  </div>
                  <p className="mt-2 font-mono text-[11px] text-slate-500">
                    {Object.entries(row.scores || {})
                      .map(([k, v]) => `${k}: ${v}`)
                      .join(' · ')}
                  </p>
                </li>
                )
              })}
            </ul>
          )}
        </div>
      )}
    </section>
  )
}
