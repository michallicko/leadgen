/**
 * ImportPage -- 3-step wizard for importing contacts from CSV or Google.
 * Ported from dashboard/import.html (1919 lines vanilla JS).
 */

import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router'
import { WizardSteps } from '../../components/ui/WizardSteps'
import { UploadStep } from './UploadStep'
import { MappingStep } from './MappingStep'
import { PreviewStep } from './PreviewStep'
import { PastImports } from './PastImports'
import type {
  ColumnMapping,
  UploadResponse,
  PreviewResponse,
  ImportResponse,
} from '../../api/queries/useImports'

interface ImportState {
  step: 1 | 2 | 3
  source: 'csv' | 'google'
  jobId: string | null
  mapping: ColumnMapping[] | null
  customFieldDefs: Array<{ field_key: string; display_name: string; source_column: string }>
  batchName: string
  ownerId: string
  dedupStrategy: 'skip' | 'update' | 'create_new'
  uploadResponse: UploadResponse | null
  previewResponse: PreviewResponse | null
  importResponse: ImportResponse | null
}

const WIZARD_STEPS = [
  { label: 'Upload' },
  { label: 'Map Columns' },
  { label: 'Preview & Import' },
]

export function ImportPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  const [state, setState] = useState<ImportState>({
    step: 1,
    source: 'csv',
    jobId: null,
    mapping: null,
    customFieldDefs: [],
    batchName: '',
    ownerId: '',
    dedupStrategy: 'skip',
    uploadResponse: null,
    previewResponse: null,
    importResponse: null,
  })

  // Handle OAuth callback: ?connected=true
  useEffect(() => {
    if (searchParams.get('connected') === 'true') {
      setState((prev) => ({ ...prev, source: 'google' }))
      // Clean URL
      const newParams = new URLSearchParams(searchParams)
      newParams.delete('connected')
      setSearchParams(newParams, { replace: true })
    }
  }, [searchParams, setSearchParams])

  const setStep = useCallback((step: 1 | 2 | 3) => {
    setState((prev) => ({ ...prev, step }))
  }, [])

  const setSource = useCallback((source: 'csv' | 'google') => {
    setState((prev) => ({ ...prev, source }))
  }, [])

  const setBatchName = useCallback((batchName: string) => {
    setState((prev) => ({ ...prev, batchName }))
  }, [])

  const setOwnerId = useCallback((ownerId: string) => {
    setState((prev) => ({ ...prev, ownerId }))
  }, [])

  const setDedupStrategy = useCallback((dedupStrategy: 'skip' | 'update' | 'create_new') => {
    setState((prev) => ({ ...prev, dedupStrategy }))
  }, [])

  const handleUploadComplete = useCallback((response: UploadResponse) => {
    setState((prev) => ({
      ...prev,
      jobId: response.job_id,
      mapping: response.columns,
      customFieldDefs: response.custom_field_defs,
      uploadResponse: response,
      step: 2,
    }))
  }, [])

  const handleGoogleComplete = useCallback((jobId: string, preview: PreviewResponse) => {
    setState((prev) => ({
      ...prev,
      jobId,
      previewResponse: preview,
      step: 3,
    }))
  }, [])

  const handleMappingComplete = useCallback((mapping: ColumnMapping[], preview: PreviewResponse) => {
    setState((prev) => ({
      ...prev,
      mapping,
      previewResponse: preview,
      step: 3,
    }))
  }, [])

  const handleRemapped = useCallback((response: UploadResponse) => {
    setState((prev) => ({
      ...prev,
      mapping: response.columns,
      customFieldDefs: response.custom_field_defs,
      uploadResponse: response,
    }))
  }, [])

  const handleImportComplete = useCallback((response: ImportResponse) => {
    setState((prev) => ({
      ...prev,
      importResponse: response,
    }))
  }, [])

  const handleResume = useCallback((jobId: string, mapping: ColumnMapping[], preview: PreviewResponse | null) => {
    setState((prev) => ({
      ...prev,
      jobId,
      mapping,
      previewResponse: preview,
      step: preview ? 3 : 2,
    }))
  }, [])

  const handleReset = useCallback(() => {
    setState({
      step: 1,
      source: 'csv',
      jobId: null,
      mapping: null,
      customFieldDefs: [],
      batchName: '',
      ownerId: '',
      dedupStrategy: 'skip',
      uploadResponse: null,
      previewResponse: null,
      importResponse: null,
    })
  }, [])

  // When source is google, step 2 (Map Columns) is skipped
  const skippedSteps = state.source === 'google' ? [1] : []

  return (
    <div className="p-6">
      {/* Page header */}
      <h1 className="font-title text-[1.3rem] font-semibold tracking-tight mb-1.5">
        Import Contacts
      </h1>
      <p className="text-text-muted text-[0.9rem] mb-6">
        Upload CSV files or connect Google accounts to import contacts
      </p>

      {/* Wizard steps indicator */}
      <div className="mb-6">
        <WizardSteps
          steps={WIZARD_STEPS}
          current={state.step - 1}
          skippedSteps={skippedSteps}
        />
      </div>

      {/* Step content */}
      <div className="bg-surface border border-border rounded-lg p-6 mb-6">
        {state.step === 1 && (
          <UploadStep
            source={state.source}
            onSourceChange={setSource}
            batchName={state.batchName}
            onBatchNameChange={setBatchName}
            ownerId={state.ownerId}
            onOwnerIdChange={setOwnerId}
            onUploadComplete={handleUploadComplete}
            onGoogleComplete={handleGoogleComplete}
          />
        )}

        {state.step === 2 && state.uploadResponse && (
          <MappingStep
            uploadResponse={state.uploadResponse}
            mapping={state.mapping!}
            jobId={state.jobId!}
            onBack={() => setStep(1)}
            onPreviewComplete={handleMappingComplete}
            onRemapped={handleRemapped}
          />
        )}

        {state.step === 3 && (
          <PreviewStep
            previewResponse={state.previewResponse}
            jobId={state.jobId!}
            source={state.source}
            dedupStrategy={state.dedupStrategy}
            onDedupStrategyChange={setDedupStrategy}
            onBack={() => setStep(state.source === 'google' ? 1 : 2)}
            onImportComplete={handleImportComplete}
            importResponse={state.importResponse}
            onReset={handleReset}
          />
        )}
      </div>

      {/* Past imports -- always visible below wizard */}
      <PastImports onResume={handleResume} />
    </div>
  )
}
