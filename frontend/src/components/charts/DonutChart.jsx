import { DONUT_COLORS } from '../../constants/buckets.js'

/** SVG donut for bucket distribution. Arc sizes use segment sums; center can show unique paper count. */
export default function DonutChart({
  segments,
  size = 180,
  className = '',
  /** Unique paper count for center label (avoids double-counting multi-bucket papers). */
  centerValue,
  centerLabel = 'papers',
}) {
  const data = (segments ?? []).filter((s) => s.value > 0)
  const segmentTotal = data.reduce((a, s) => a + s.value, 0)
  const arcTotal = segmentTotal
  const r = 38
  const cx = 50
  const cy = 50
  const stroke = 14
  const circ = 2 * Math.PI * r

  if (arcTotal === 0) {
    return (
      <div
        className={`flex items-center justify-center rounded-full text-sm text-slate-400 ${className}`}
        style={{ width: size, height: size }}
      >
        No papers
      </div>
    )
  }

  let offset = 0
  const arcs = data.map((seg, i) => {
    const frac = seg.value / arcTotal
    const dash = frac * circ
    const gap = circ - dash
    const el = (
      <circle
        key={seg.label}
        cx={cx}
        cy={cy}
        r={r}
        fill="none"
        stroke={seg.color || DONUT_COLORS[i % DONUT_COLORS.length]}
        strokeWidth={stroke}
        strokeDasharray={`${dash} ${gap}`}
        strokeDashoffset={-offset}
        transform={`rotate(-90 ${cx} ${cy})`}
      />
    )
    offset += dash
    return el
  })

  return (
    <div className={`relative inline-flex ${className}`} style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100" className="h-full w-full" role="img" aria-label="Bucket distribution">
        {arcs}
      </svg>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold tabular-nums text-slate-900">
          {centerValue != null ? centerValue : arcTotal}
        </span>
        <span className="text-[10px] font-medium uppercase tracking-wide text-slate-500">{centerLabel}</span>
      </div>
    </div>
  )
}
