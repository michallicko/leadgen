/**
 * Placeholder for pages not yet ported from vanilla JS.
 */

interface Props {
  title: string
  description?: string
}

export function PlaceholderPage({ title, description }: Props) {
  return (
    <div>
      <h1 className="font-title text-[1.3rem] font-semibold tracking-tight mb-1.5">{title}</h1>
      <p className="text-text-muted text-[0.9rem] mb-6">
        {description ?? 'This page is being ported to the new React frontend.'}
      </p>
      <div className="bg-surface border border-border rounded-lg p-8 text-center text-text-muted">
        <div className="text-3xl mb-2">🚧</div>
        <div className="text-[0.85rem]">Coming soon — migration in progress</div>
      </div>
    </div>
  )
}
