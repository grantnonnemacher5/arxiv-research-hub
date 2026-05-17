/** Fill missing calendar days with count 0 for area charts. */
export function fillDailySeries(points, days) {
  const map = new Map((points ?? []).map((p) => [p.date, p.count]))
  const out = []
  const end = new Date()
  end.setHours(12, 0, 0, 0)
  for (let i = days - 1; i >= 0; i -= 1) {
    const d = new Date(end)
    d.setDate(d.getDate() - i)
    const key = d.toISOString().slice(0, 10)
    out.push({ date: key, count: map.get(key) ?? 0 })
  }
  return out
}
