const STYLES = {
  'General AI': 'bg-blue-50 text-blue-800 ring-1 ring-blue-100',
  'Autonomous Agents': 'bg-sky-50 text-sky-800 ring-1 ring-sky-100',
  'AI x Finance': 'bg-emerald-50 text-emerald-800 ring-1 ring-emerald-100',
  Unclassified: 'bg-amber-200 text-stone-900 ring-1 ring-amber-400/80 font-semibold',
}

/** Pastel ring for unknown bucket strings from the API */
const FALLBACK_BADGE = [
  'bg-fuchsia-50 text-fuchsia-900 ring-1 ring-fuchsia-100',
  'bg-cyan-50 text-cyan-900 ring-1 ring-cyan-100',
  'bg-lime-50 text-lime-900 ring-1 ring-lime-100',
  'bg-rose-50 text-rose-900 ring-1 ring-rose-100',
]

function fallbackClass(label) {
  let h = 0
  for (let i = 0; i < label.length; i += 1) h = (h + label.charCodeAt(i) * (i + 1)) % 997
  return FALLBACK_BADGE[h % FALLBACK_BADGE.length]
}

export default function CategoryBadge({ label }) {
  const cls = STYLES[label] || fallbackClass(label)
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {label}
    </span>
  )
}
