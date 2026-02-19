/**
 * GoogleConnect -- Google OAuth panel for importing contacts from Google Contacts / Gmail.
 */

import { useState, useEffect, useCallback } from 'react'
import {
  getOAuthConnections,
  getGoogleAuthUrl,
  deleteConnection,
  fetchGoogleContacts,
  startGmailScan,
  googlePreview,
} from '../../api/queries/useImports'
import type { OAuthConnection, PreviewResponse } from '../../api/queries/useImports'

interface GoogleConnectProps {
  batchName: string
  onBatchNameChange: (name: string) => void
  onComplete: (jobId: string, preview: PreviewResponse) => void
}

export function GoogleConnect({ batchName, onBatchNameChange, onComplete }: GoogleConnectProps) {
  const [connections, setConnections] = useState<OAuthConnection[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isFetching, setIsFetching] = useState(false)
  const [fetchStatus, setFetchStatus] = useState('')
  const [error, setError] = useState<string | null>(null)

  // Source checkboxes
  const [useContacts, setUseContacts] = useState(true)
  const [useGmail, setUseGmail] = useState(false)

  // Gmail config
  const [dateRange, setDateRange] = useState('90')
  const [excludeDomains, setExcludeDomains] = useState('')

  const loadConnections = useCallback(async () => {
    try {
      setIsLoading(true)
      const data = await getOAuthConnections()
      setConnections(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load connections')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadConnections()
  }, [loadConnections])

  const activeConnection = connections.find((c) => c.provider === 'google')

  const handleConnect = useCallback(async () => {
    try {
      const data = await getGoogleAuthUrl(window.location.href)
      window.location.href = data.auth_url
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start OAuth')
    }
  }, [])

  const handleDisconnect = useCallback(async () => {
    if (!activeConnection) return
    try {
      await deleteConnection(activeConnection.id)
      await loadConnections()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Disconnect failed')
    }
  }, [activeConnection, loadConnections])

  const handleFetch = useCallback(async () => {
    if (!activeConnection) return
    if (!useContacts && !useGmail) {
      setError('Select at least one source')
      return
    }

    // Auto-generate batch name if empty
    if (!batchName) {
      onBatchNameChange('google-import-' + new Date().toISOString().slice(0, 10))
    }

    setError(null)
    setIsFetching(true)
    let jobId: string | null = null

    try {
      // Fetch Google Contacts if selected
      if (useContacts) {
        setFetchStatus('Fetching contacts from Google...')
        const contactsResult = await fetchGoogleContacts(activeConnection.id)
        jobId = contactsResult.job_id
      }

      // Start Gmail scan if selected
      if (useGmail) {
        setFetchStatus('Scanning Gmail messages...')
        const domains = excludeDomains
          ? excludeDomains.split(',').map((s) => s.trim()).filter(Boolean)
          : []
        const scanResult = await startGmailScan({
          connection_id: activeConnection.id,
          date_range: dateRange,
          exclude_domains: domains,
        })
        // Prefer Gmail job if it found contacts
        if (scanResult.contacts_found > 0) {
          jobId = scanResult.job_id
        } else if (!jobId) {
          jobId = scanResult.job_id
        }
      }

      if (!jobId) {
        setError('No contacts found')
        setIsFetching(false)
        return
      }

      // Run preview
      setFetchStatus('Generating preview...')
      const preview = await googlePreview(jobId)
      setIsFetching(false)
      onComplete(jobId, preview)
    } catch (err) {
      setIsFetching(false)
      setError(err instanceof Error ? err.message : 'Fetch failed')
    }
  }, [activeConnection, useContacts, useGmail, dateRange, excludeDomains, batchName, onBatchNameChange, onComplete])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-3 p-8 text-text-muted">
        <div className="w-5 h-5 border-2 border-border border-t-accent-cyan rounded-full animate-spin" />
        <span className="text-sm">Loading connections...</span>
      </div>
    )
  }

  if (isFetching) {
    return (
      <div className="flex items-center justify-center gap-3 p-8 text-text-muted">
        <div className="w-6 h-6 border-2 border-border border-t-accent-cyan rounded-full animate-spin" />
        <span className="text-sm">{fetchStatus}</span>
      </div>
    )
  }

  // Not connected
  if (!activeConnection) {
    return (
      <div className="text-center py-6">
        <p className="text-text-muted text-sm mb-4">
          Connect your Google account to import contacts from Gmail or Google Contacts.
        </p>
        <button
          onClick={handleConnect}
          className="inline-flex items-center gap-2.5 bg-white text-[#3c4043] font-semibold border border-[#dadce0] rounded-md px-5 py-2.5 cursor-pointer hover:shadow-md transition-shadow"
        >
          <svg width="18" height="18" viewBox="0 0 48 48">
            <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
            <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
            <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
            <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
          </svg>
          Sign in with Google
        </button>

        {error && (
          <div className="mt-4 bg-red-400/10 border border-red-400/20 rounded-md px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}
      </div>
    )
  }

  // Connected
  return (
    <div>
      {/* Connected account row */}
      <div className="flex items-center gap-3 bg-surface-alt rounded-lg px-4 py-3 mb-4">
        <span className="w-2 h-2 rounded-full bg-green-400 flex-shrink-0" />
        <span className="text-sm font-medium text-text flex-1 truncate">
          {activeConnection.email}
        </span>
        <button
          onClick={handleDisconnect}
          className="border border-border text-text-muted px-3 py-1 rounded-md hover:bg-surface-alt transition-colors text-xs"
        >
          Disconnect
        </button>
      </div>

      {/* Source checkboxes */}
      <div className="flex gap-3 mb-4">
        <label
          className={`flex items-center gap-2 text-sm cursor-pointer px-4 py-2.5 border rounded-md transition-colors ${
            useContacts
              ? 'border-accent-cyan text-text bg-accent-cyan/5'
              : 'border-border-solid text-text-muted hover:border-accent-cyan hover:text-text'
          }`}
        >
          <input
            type="checkbox"
            checked={useContacts}
            onChange={(e) => setUseContacts(e.target.checked)}
            className="accent-accent-cyan w-4 h-4"
          />
          Google Contacts
        </label>
        <label
          className={`flex items-center gap-2 text-sm cursor-pointer px-4 py-2.5 border rounded-md transition-colors ${
            useGmail
              ? 'border-accent-cyan text-text bg-accent-cyan/5'
              : 'border-border-solid text-text-muted hover:border-accent-cyan hover:text-text'
          }`}
        >
          <input
            type="checkbox"
            checked={useGmail}
            onChange={(e) => setUseGmail(e.target.checked)}
            className="accent-accent-cyan w-4 h-4"
          />
          Gmail Emails
        </label>
      </div>

      {/* Gmail scan config */}
      {useGmail && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-xs text-text-muted font-medium mb-1.5">
              Date Range
            </label>
            <select
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              className="w-full bg-surface-alt border border-border rounded-md px-3 py-2 text-sm text-text focus:outline-none focus:border-accent-cyan"
            >
              <option value="30">Last 30 days</option>
              <option value="90">Last 90 days</option>
              <option value="180">Last 6 months</option>
              <option value="365">Last 1 year</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-text-muted font-medium mb-1.5">
              Exclude Domains (comma-separated)
            </label>
            <input
              type="text"
              value={excludeDomains}
              onChange={(e) => setExcludeDomains(e.target.value)}
              placeholder="gmail.com, yahoo.com"
              className="w-full bg-surface-alt border border-border rounded-md px-3 py-2 text-sm text-text placeholder:text-text-dim focus:outline-none focus:border-accent-cyan"
            />
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mb-4 bg-red-400/10 border border-red-400/20 rounded-md px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Fetch button */}
      <button
        onClick={handleFetch}
        disabled={!useContacts && !useGmail}
        className="bg-accent-cyan text-bg font-semibold px-5 py-2.5 rounded-md hover:opacity-90 transition-opacity text-sm disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Fetch & Preview
      </button>
    </div>
  )
}
