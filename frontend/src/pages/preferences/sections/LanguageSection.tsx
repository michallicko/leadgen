/**
 * LanguageSection -- namespace-level language and enrichment language settings.
 */

import { useReducer } from 'react'
import { useNamespace } from '../../../hooks/useNamespace'
import { useTenantBySlug, usePatchTenantSettings } from '../../../api/queries/useAdmin'
import { LANGUAGES } from '../../../lib/languages'
import { useToast } from '../../../components/ui/Toast'

interface FormState {
  language: string
  enrichmentLanguage: string
  dirty: boolean
  /** Tracks which tenant data snapshot the form was derived from. */
  settingsKey: string
}

type FormAction =
  | { type: 'set_language'; value: string }
  | { type: 'set_enrichment_language'; value: string }
  | { type: 'saved' }

function formReducer(state: FormState, action: FormAction): FormState {
  switch (action.type) {
    case 'set_language':
      return { ...state, language: action.value, dirty: true }
    case 'set_enrichment_language':
      return { ...state, enrichmentLanguage: action.value, dirty: true }
    case 'saved':
      return { ...state, dirty: false }
  }
}

function buildInitialState(language: string, enrichmentLanguage: string, key: string): FormState {
  return { language, enrichmentLanguage, dirty: false, settingsKey: key }
}

export function LanguageSection() {
  const namespace = useNamespace()
  const { tenant, isLoading } = useTenantBySlug(namespace)
  const patchSettings = usePatchTenantSettings()
  const { toast } = useToast()

  // Derive initial values from tenant; reset form when tenant data changes
  const serverLanguage = tenant?.settings?.language ?? 'en'
  const serverEnrichment = tenant?.settings?.enrichment_language ?? ''
  const settingsKey = `${tenant?.id}-${serverLanguage}-${serverEnrichment}`

  const [form, dispatch] = useReducer(
    formReducer,
    buildInitialState(serverLanguage, serverEnrichment, settingsKey),
  )

  // Reset form when server data changes (e.g. after save or external update)
  const staleForm = form.settingsKey !== settingsKey && !form.dirty
  const state = staleForm
    ? buildInitialState(serverLanguage, serverEnrichment, settingsKey)
    : form

  const handleSave = () => {
    if (!tenant) return

    const settings: Record<string, string | null> = {
      language: state.language,
    }
    settings.enrichment_language = state.enrichmentLanguage || null

    patchSettings.mutate(
      { tenantId: tenant.id, settings },
      {
        onSuccess: () => {
          toast('Language settings saved', 'success')
          dispatch({ type: 'saved' })
        },
        onError: (err) => {
          const msg = err instanceof Error ? err.message : 'Unknown error'
          toast(`Failed to save: ${msg}`, 'error')
        },
      },
    )
  }

  if (isLoading) {
    return (
      <div className="bg-surface border border-border rounded-lg p-5">
        <p className="text-text-muted text-sm">Loading language settings...</p>
      </div>
    )
  }

  if (!tenant) {
    return (
      <div className="bg-surface border border-border rounded-lg p-5">
        <p className="text-text-muted text-sm">Namespace not found.</p>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <div className="bg-surface border border-border rounded-lg p-5">
        <h2 className="font-title text-[1rem] font-semibold tracking-tight mb-1">
          Language
        </h2>
        <p className="text-text-muted text-sm mb-4">
          Set the default language for this namespace. This affects playbook chat responses
          and new contact defaults.
        </p>

        <div className="space-y-4">
          {/* Primary language */}
          <div>
            <label
              htmlFor="lang-select"
              className="block text-sm font-medium text-text mb-1.5"
            >
              Default language
            </label>
            <select
              id="lang-select"
              value={state.language}
              onChange={(e) => dispatch({ type: 'set_language', value: e.target.value })}
              className="w-full max-w-[280px] bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-accent"
            >
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
          </div>

          {/* Enrichment language override */}
          <div>
            <label
              htmlFor="enrich-lang-select"
              className="block text-sm font-medium text-text mb-1.5"
            >
              Enrichment language
              <span className="text-text-muted font-normal ml-1">(optional)</span>
            </label>
            <p className="text-text-muted text-xs mb-1.5">
              Override the language used for AI enrichment research. If not set, the default
              language above is used.
            </p>
            <select
              id="enrich-lang-select"
              value={state.enrichmentLanguage}
              onChange={(e) =>
                dispatch({ type: 'set_enrichment_language', value: e.target.value })
              }
              className="w-full max-w-[280px] bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-accent"
            >
              <option value="">Same as default language</option>
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Save button */}
        <div className="mt-5 flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={!state.dirty || patchSettings.isPending}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-accent text-white hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {patchSettings.isPending ? 'Saving...' : 'Save'}
          </button>
          {state.dirty && (
            <span className="text-text-muted text-xs">Unsaved changes</span>
          )}
        </div>
      </div>
    </div>
  )
}
