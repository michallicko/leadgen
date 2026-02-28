/**
 * GeneralSection -- browser extension status (extracted from original PreferencesPage).
 */

import { useEffect, useState } from 'react'
import { apiFetch } from '../../../api/client'

interface ExtensionStatus {
  connected: boolean
  last_lead_sync: string | null
  last_activity_sync: string | null
  total_leads_imported: number
  total_activities_synced: number
}

export function GeneralSection() {
  const [status, setStatus] = useState<ExtensionStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<ExtensionStatus>('/extension/status')
      .then(setStatus)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <div className="bg-surface border border-border rounded-lg p-5">
        <h2 className="font-title text-[1rem] font-semibold tracking-tight mb-4">
          Browser Extension
        </h2>

        {loading && (
          <p className="text-text-muted text-sm">Loading extension status...</p>
        )}

        {error && (
          <p className="text-error text-sm">
            Failed to load extension status: {error}
          </p>
        )}

        {!loading && !error && status && (
          <>
            <div className="flex items-center gap-2 mb-4">
              <span
                className={`inline-block w-2.5 h-2.5 rounded-full ${
                  status.connected ? 'bg-green-500' : 'bg-text-muted/40'
                }`}
              />
              <span className="text-sm text-text">
                {status.connected ? 'Connected' : 'Not connected'}
              </span>
              {status.connected && status.last_lead_sync && (
                <span className="text-[0.75rem] text-text-muted ml-2">
                  Last sync {formatRelative(status.last_lead_sync)}
                </span>
              )}
            </div>

            {status.connected && (
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div className="bg-surface-alt rounded-md p-3">
                  <dt className="text-text-muted text-[0.75rem] mb-1">Leads imported</dt>
                  <dd className="text-[1.1rem] font-semibold text-text">{status.total_leads_imported}</dd>
                </div>
                <div className="bg-surface-alt rounded-md p-3">
                  <dt className="text-text-muted text-[0.75rem] mb-1">Activities synced</dt>
                  <dd className="text-[1.1rem] font-semibold text-text">{status.total_activities_synced}</dd>
                </div>
                <div className="bg-surface-alt rounded-md p-3">
                  <dt className="text-text-muted text-[0.75rem] mb-1">Last lead sync</dt>
                  <dd className="text-text text-[0.82rem]">
                    {status.last_lead_sync ? formatDate(status.last_lead_sync) : '\u2014'}
                  </dd>
                </div>
                <div className="bg-surface-alt rounded-md p-3">
                  <dt className="text-text-muted text-[0.75rem] mb-1">Last activity sync</dt>
                  <dd className="text-text text-[0.82rem]">
                    {status.last_activity_sync ? formatDate(status.last_activity_sync) : '\u2014'}
                  </dd>
                </div>
              </div>
            )}

            {!status.connected && (
              <p className="text-text-muted text-sm">
                Install the VisionVolve Leads browser extension and log in to connect.
                Once connected, your lead imports and activity syncs will appear here.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString()
}

function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}
