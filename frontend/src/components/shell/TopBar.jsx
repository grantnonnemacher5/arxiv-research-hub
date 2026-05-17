import { PAGE_LABELS } from './Sidebar.jsx'

export default function TopBar({ page }) {
  const label = PAGE_LABELS[page] || 'Research hub'
  return (
    <header className="z-10 flex h-14 shrink-0 items-center border-b border-slate-200 bg-white px-6">
      <p className="text-sm text-slate-500">
        <span className="text-slate-400">Research hub</span>
        <span className="mx-2 text-slate-300">›</span>
        <span className="font-medium text-slate-800">{label}</span>
      </p>
    </header>
  )
}
