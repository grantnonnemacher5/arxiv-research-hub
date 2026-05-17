import Sidebar from './Sidebar.jsx'
import TopBar from './TopBar.jsx'

export default function AppShell({
  activePage,
  onNavigate,
  paperCount,
  syncBanner,
  toast,
  onDismissToast,
  children,
}) {
  return (
    <div className="flex h-screen overflow-hidden bg-[#f4f5f7] font-sans text-slate-700 antialiased">
      <Sidebar activePage={activePage} onNavigate={onNavigate} paperCount={paperCount} />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <TopBar page={activePage} />
        {syncBanner}
        {toast ? (
          <div
            role="status"
            className={`mx-6 mt-4 rounded-lg border px-4 py-3 text-sm ${
              toast.type === 'ok'
                ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                : 'border-red-200 bg-red-50 text-red-900'
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <span>{toast.text}</span>
              <button
                type="button"
                onClick={onDismissToast}
                className="shrink-0 text-xs font-semibold opacity-70 hover:opacity-100"
              >
                Dismiss
              </button>
            </div>
          </div>
        ) : null}
        <main className="min-h-0 flex-1 overflow-y-auto bg-[#f4f5f7]">{children}</main>
      </div>
    </div>
  )
}
