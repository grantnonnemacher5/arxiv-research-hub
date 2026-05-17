import { IconDashboard, IconHub, IconPapers, IconPipeline, IconReports } from './icons.jsx'

const NAV = [
  { id: 'dashboard', label: 'Dashboard', Icon: IconDashboard },
  { id: 'reports', label: 'Reports', Icon: IconReports },
  { id: 'papers', label: 'Papers', Icon: IconPapers, badgeKey: 'papers' },
  { id: 'pipeline', label: 'Pipeline', Icon: IconPipeline },
]

export const PAGE_LABELS = {
  dashboard: 'Dashboard',
  reports: 'Reports',
  papers: 'Papers',
  pipeline: 'Pipeline',
}

export default function Sidebar({ activePage, onNavigate, paperCount }) {
  return (
    <aside className="flex h-full w-[282px] shrink-0 flex-col border-r border-slate-200/80 bg-white">
      <div className="px-4 pb-3 pt-5">
        <div className="flex items-center gap-2.5">
          <IconHub className="h-7 w-7" />
          <div className="min-w-0">
            <p className="truncate text-[13px] font-bold leading-tight text-slate-900">Research hub</p>
            <p className="truncate text-[10px] leading-tight text-slate-500">arXiv Intelligence MVP</p>
          </div>
        </div>
      </div>

      <p className="px-4 pb-1 pt-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
        Navigation
      </p>

      <nav className="flex flex-col gap-1 px-3 pb-4" aria-label="Main">
        {NAV.map(({ id, label, Icon, badgeKey }) => {
          const active = activePage === id
          return (
            <button
              key={id}
              type="button"
              onClick={() => onNavigate(id)}
              className={`flex w-full min-h-[2.75rem] items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium transition ${
                active
                  ? 'bg-sky-50 text-sky-700'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              <Icon
                className={`h-5 w-5 shrink-0 ${active ? 'text-sky-600' : 'text-slate-400'}`}
              />
              <span className="min-w-0 flex-1 truncate">{label}</span>
              {badgeKey === 'papers' && paperCount != null ? (
                <span
                  className={`shrink-0 rounded-md px-2 py-0.5 text-xs font-semibold tabular-nums ${
                    active ? 'bg-sky-100 text-sky-800' : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {paperCount}
                </span>
              ) : null}
            </button>
          )
        })}
      </nav>
    </aside>
  )
}
