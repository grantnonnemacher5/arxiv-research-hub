import PaperList from '../components/PaperList.jsx'
import PaperSearch from '../components/PaperSearch.jsx'
import { PAGE_SHELL } from '../constants/layout.js'

export default function PapersPage({ refreshKey, onToast }) {
  return (
    <div className={PAGE_SHELL}>
      <header className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Papers</h1>
        <p className="mt-1.5 text-sm text-slate-500">
          Search corpus above, then browse and filter the full library below.
        </p>
      </header>
      <div className="flex flex-col gap-6 lg:gap-8">
        <PaperSearch />
        <PaperList refreshKey={refreshKey} onToast={onToast} />
      </div>
    </div>
  )
}
