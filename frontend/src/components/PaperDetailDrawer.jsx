import { useEffect } from 'react'
import CategoryBadge from './CategoryBadge.jsx'

function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

function badgesFor(buckets) {
  return (buckets || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
}

export default function PaperDetailDrawer({ paper, onClose }) {
  useEffect(() => {
    if (!paper) return undefined
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = prev
      window.removeEventListener('keydown', onKey)
    }
  }, [paper, onClose])

  if (!paper) return null

  const tags = badgesFor(paper.buckets)
  const pdf = paper.pdf_url?.trim()

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        className="absolute inset-0 bg-slate-900/25 backdrop-blur-[1px] transition-opacity"
        aria-label="Close panel"
        onClick={onClose}
      />
      <div
        className="relative flex h-full w-full max-w-lg flex-col border-l border-slate-200 bg-white shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="paper-detail-title"
      >
        <div className="flex shrink-0 items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
          <p className="text-xs font-medium uppercase tracking-wide text-sky-600">Paper detail</p>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
            aria-label="Close"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
          <div className="flex flex-wrap gap-2">
            {tags.length > 0 ? (
              tags.map((b) => <CategoryBadge key={b} label={b} />)
            ) : (
              <CategoryBadge label="Unclassified" />
            )}
          </div>

          <h2
            id="paper-detail-title"
            className="mt-4 text-xl font-semibold leading-snug tracking-tight text-slate-900 sm:text-2xl"
          >
            {paper.title}
          </h2>
          <p className="mt-3 text-sm font-medium leading-relaxed text-slate-600">{paper.authors}</p>
          <p className="mt-2 font-mono text-xs text-slate-400">
            {paper.arxiv_id}
            <span className="mx-2 text-slate-300">·</span>
            Published {formatDate(paper.published_date)}
            <span className="mx-2 text-slate-300">·</span>
            Ingested {formatDate(paper.created_at)}
          </p>

          <div className="mt-6 space-y-6">
            <section>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Abstract</h3>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                {paper.abstract?.trim() || 'No abstract stored for this paper.'}
              </p>
            </section>

            <section>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Bucket classification</h3>
              <p className="mt-2 text-sm text-slate-700">
                {tags.length > 0 ? (
                  <span>
                    This paper is tagged as: <strong>{tags.join(', ')}</strong>.
                  </span>
                ) : (
                  <span className="text-amber-800">
                    Not yet classified. Run the pipeline with classification enabled, or sync again after
                    embeddings are configured.
                  </span>
                )}
              </p>
            </section>

            <section className="rounded-xl border border-slate-200 bg-slate-50/80 px-4 py-3">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">AI summary</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">
                Per-paper AI summaries are not stored in this MVP. Thematic summaries by bucket appear in the
                HTML reports you generate (7d, 1m, …) from the Export report section.
              </p>
            </section>

            {pdf ? (
              <a
                href={pdf}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-lg bg-sky-500 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-600"
              >
                Open PDF
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </a>
            ) : (
              <p className="text-sm text-slate-500">No PDF link on file.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
