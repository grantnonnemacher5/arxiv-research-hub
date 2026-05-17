function cn(...parts) {
  return parts.filter(Boolean).join(' ')
}

export function IconDashboard({ className = '' }) {
  return (
    <svg className={cn('h-4 w-4 shrink-0', className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
    </svg>
  )
}

export function IconReports({ className = '' }) {
  return (
    <svg className={cn('h-4 w-4 shrink-0', className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M9 12h6M9 16h6M9 8h6" strokeLinecap="round" />
      <path d="M6 4h9l3 3v13H6V4z" strokeLinejoin="round" />
    </svg>
  )
}

export function IconPapers({ className = '' }) {
  return (
    <svg className={cn('h-4 w-4 shrink-0', className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M8 4h11v16H8V4z" />
      <path d="M5 7H8M5 11H8M5 15H8" strokeLinecap="round" />
    </svg>
  )
}

export function IconPipeline({ className = '' }) {
  return (
    <svg className={cn('h-4 w-4 shrink-0', className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M4 6h6v4H4V6zM14 6h6v4h-6V6zM9 14h6v4H9v-4z" strokeLinejoin="round" />
    </svg>
  )
}

export function IconSearch({ className = '' }) {
  return (
    <svg className={cn('h-4 w-4 shrink-0', className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.3-4.3" strokeLinecap="round" />
    </svg>
  )
}

export function IconHub({ className = '' }) {
  return (
    <svg className={cn('h-8 w-8 shrink-0', className)} viewBox="0 0 32 32" fill="none">
      <rect width="32" height="32" rx="8" className="fill-sky-600" />
      <path
        d="M10 16c0-3.3 2.7-6 6-6s6 2.7 6 6-2.7 6-6 6"
        stroke="white"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <circle cx="16" cy="16" r="2" fill="white" />
    </svg>
  )
}
