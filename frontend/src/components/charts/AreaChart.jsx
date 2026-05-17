/** Lightweight SVG area chart — no chart library dependency. */
export default function AreaChart({ series, height = 200, className = '' }) {
  const data = series ?? []
  const w = 640
  const h = height
  const pad = { top: 12, right: 12, bottom: 28, left: 36 }
  const innerW = w - pad.left - pad.right
  const innerH = h - pad.top - pad.bottom

  if (data.length === 0) {
    return (
      <div
        className={`flex items-center justify-center text-sm text-slate-400 ${className}`}
        style={{ height }}
      >
        No data yet
      </div>
    )
  }

  const maxY = Math.max(1, ...data.map((d) => d.count))
  const n = data.length

  const pts = data.map((d, i) => {
    const x = pad.left + (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW)
    const y = pad.top + innerH - (d.count / maxY) * innerH
    return { x, y, ...d }
  })

  const linePath = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')
  const areaPath = `${linePath} L ${pts[pts.length - 1].x} ${pad.top + innerH} L ${pts[0].x} ${pad.top + innerH} Z`

  const yTicks = [0, Math.ceil(maxY / 2), maxY]
  const labelEvery = Math.max(1, Math.floor(n / 6))
  const xLabels = pts.filter((_, i) => i % labelEvery === 0 || i === n - 1)

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className={`w-full max-w-full ${className}`}
      role="img"
      aria-label="Papers published over time"
    >
      <defs>
        <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {yTicks.map((tick) => {
        const y = pad.top + innerH - (tick / maxY) * innerH
        return (
          <g key={tick}>
            <line
              x1={pad.left}
              y1={y}
              x2={w - pad.right}
              y2={y}
              stroke="#e2e8f0"
              strokeWidth="1"
            />
            <text x={pad.left - 6} y={y + 4} textAnchor="end" className="fill-slate-400 text-[10px]">
              {tick}
            </text>
          </g>
        )
      })}
      <path d={areaPath} fill="url(#areaFill)" />
      <path d={linePath} fill="none" stroke="#0ea5e9" strokeWidth="2" strokeLinejoin="round" />
      {xLabels.map((p) => (
        <text
          key={p.date}
          x={p.x}
          y={h - 8}
          textAnchor="middle"
          className="fill-slate-400 text-[9px]"
        >
          {p.date.slice(5)}
        </text>
      ))}
    </svg>
  )
}
