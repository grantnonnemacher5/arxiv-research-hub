/** Research buckets — keys match `classifier.BUCKET_DESCRIPTIONS` and API `stats.buckets`. */
export const RESEARCH_BUCKETS = [
  {
    key: 'General AI',
    label: 'General AI',
    dotClass: 'bg-blue-500',
    barClass: 'bg-blue-500',
    chipClass: 'bg-blue-50 text-blue-800 ring-blue-100',
    iconBox: 'bg-sky-100 text-sky-600',
    categories: ['cs.AI', 'cs.LG'],
  },
  {
    key: 'Autonomous Agents',
    label: 'Autonomous Agents',
    dotClass: 'bg-emerald-500',
    barClass: 'bg-emerald-500',
    chipClass: 'bg-emerald-50 text-emerald-800 ring-emerald-100',
    iconBox: 'bg-emerald-100 text-emerald-600',
    categories: ['cs.MA', 'cs.NE'],
  },
  {
    key: 'AI x Finance',
    label: 'AI x Finance',
    dotClass: 'bg-amber-500',
    barClass: 'bg-amber-500',
    chipClass: 'bg-amber-50 text-amber-900 ring-amber-100',
    iconBox: 'bg-amber-100 text-amber-700',
    categories: ['q-fin.CP', 'q-fin.ST', 'q-fin.TR'],
  },
]

export const DONUT_COLORS = ['#3b82f6', '#10b981', '#f59e0b']
