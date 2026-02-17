export function OutreachTab() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-12 h-12 rounded-full bg-surface-alt flex items-center justify-center mb-4">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-text-dim">
          <path d="M22 2L11 13" />
          <path d="M22 2L15 22L11 13L2 9L22 2Z" />
        </svg>
      </div>
      <p className="text-sm font-medium text-text-muted">Outreach Delivery</p>
      <p className="text-xs text-text-dim mt-1">Coming soon — schedule and track message delivery</p>
    </div>
  )
}
