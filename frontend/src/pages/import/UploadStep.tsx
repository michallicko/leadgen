/**
 * UploadStep -- Step 1 of import wizard: source selection + file upload or Google connect.
 */

import { useState, useRef, useCallback } from 'react'
import { useTags } from '../../api/queries/useTags'
import { uploadFile } from '../../api/queries/useImports'
import { GoogleConnect } from './GoogleConnect'
import type { UploadResponse, PreviewResponse } from '../../api/queries/useImports'

interface UploadStepProps {
  source: 'csv' | 'google'
  onSourceChange: (source: 'csv' | 'google') => void
  batchName: string
  onBatchNameChange: (name: string) => void
  ownerId: string
  onOwnerIdChange: (id: string) => void
  onUploadComplete: (response: UploadResponse) => void
  onGoogleComplete: (jobId: string, preview: PreviewResponse) => void
}

const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB

export function UploadStep({
  source,
  onSourceChange,
  batchName,
  onBatchNameChange,
  ownerId,
  onOwnerIdChange,
  onUploadComplete,
  onGoogleComplete,
}: UploadStepProps) {
  const { data: tagsData } = useTags()
  const owners = tagsData?.owners ?? []

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const validateFile = useCallback((file: File): string | null => {
    const validExtension = /\.(csv|xlsx)$/i.test(file.name)
    const validMime = ['text/csv', 'application/csv', 'text/plain',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'].includes(file.type)
    if (!validExtension && !validMime) {
      return 'Only CSV and XLSX files are supported'
    }
    if (file.size > MAX_FILE_SIZE) {
      return 'File too large (max 10 MB)'
    }
    return null
  }, [])

  const handleFileSelected = useCallback((file: File) => {
    const validationError = validateFile(file)
    if (validationError) {
      setError(validationError)
      return
    }
    setError(null)
    setSelectedFile(file)

    // Auto-generate batch name if empty
    if (!batchName) {
      const baseName = file.name
        .replace(/\.(csv|xlsx)$/i, '')
        .replace(/[^a-zA-Z0-9_-]/g, '-')
        .toLowerCase()
      onBatchNameChange('import-' + baseName)
    }
  }, [validateFile, batchName, onBatchNameChange])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    if (e.dataTransfer.files.length) {
      handleFileSelected(e.dataTransfer.files[0])
    }
  }, [handleFileSelected])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(true)
  }, [])

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false)
  }, [])

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) {
      handleFileSelected(e.target.files[0])
    }
  }, [handleFileSelected])

  const handleUpload = useCallback(async () => {
    if (!selectedFile || !batchName) return
    setError(null)
    setIsUploading(true)
    try {
      const response = await uploadFile(selectedFile, batchName, ownerId)
      onUploadComplete(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setIsUploading(false)
    }
  }, [selectedFile, batchName, ownerId, onUploadComplete])

  const removeFile = useCallback(() => {
    setSelectedFile(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }, [])

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  return (
    <div>
      {/* Source tabs */}
      <div className="flex mb-5">
        <button
          className={`flex-1 py-3 px-4 text-center text-sm font-semibold border rounded-l-lg transition-colors ${
            source === 'csv'
              ? 'text-accent-cyan border-accent-cyan bg-accent-cyan/5'
              : 'text-text-muted border-border-solid bg-surface hover:bg-surface-alt'
          }`}
          onClick={() => onSourceChange('csv')}
        >
          CSV / Excel File
        </button>
        <button
          className={`flex-1 py-3 px-4 text-center text-sm font-semibold border border-l-0 rounded-r-lg transition-colors ${
            source === 'google'
              ? 'text-accent-cyan border-accent-cyan bg-accent-cyan/5'
              : 'text-text-muted border-border-solid bg-surface hover:bg-surface-alt'
          }`}
          onClick={() => onSourceChange('google')}
        >
          Google Account
        </button>
      </div>

      {/* CSV panel */}
      {source === 'csv' && (
        <div>
          {/* Drop zone */}
          {!selectedFile && !isUploading && (
            <div
              className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors cursor-pointer ${
                isDragOver
                  ? 'border-accent-cyan bg-accent-cyan/5'
                  : 'border-border hover:border-accent-cyan'
              }`}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.xlsx"
                className="hidden"
                onChange={handleInputChange}
              />
              <div className="text-4xl mb-3 opacity-50">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mx-auto text-text-muted">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="12" y1="18" x2="12" y2="12" />
                  <line x1="9" y1="15" x2="15" y2="15" />
                </svg>
              </div>
              <div className="text-[0.95rem] text-text-muted mb-1.5">
                Drop your file here or click to browse
              </div>
              <div className="text-xs text-text-dim">
                Max 10 MB. CSV (UTF-8/Latin-1) or Excel (.xlsx).
              </div>
            </div>
          )}

          {/* Selected file display */}
          {selectedFile && !isUploading && (
            <div className="flex items-center gap-3 bg-surface-alt rounded-lg p-4 mb-4">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-accent-cyan flex-shrink-0">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-text truncate">{selectedFile.name}</div>
                <div className="text-xs text-text-muted">{formatFileSize(selectedFile.size)}</div>
              </div>
              <button
                onClick={removeFile}
                className="text-text-dim hover:text-red-400 transition-colors p-1"
                aria-label="Remove file"
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M4 4l8 8M12 4l-8 8" />
                </svg>
              </button>
            </div>
          )}

          {/* Uploading spinner */}
          {isUploading && (
            <div className="flex items-center justify-center gap-3 p-8 text-text-muted">
              <div className="w-6 h-6 border-2 border-border border-t-accent-cyan rounded-full animate-spin" />
              <span className="text-sm">AI is analyzing your columns...</span>
            </div>
          )}
        </div>
      )}

      {/* Google panel */}
      {source === 'google' && (
        <GoogleConnect
          batchName={batchName}
          onBatchNameChange={onBatchNameChange}
          onComplete={onGoogleComplete}
        />
      )}

      {/* Shared: batch name + owner */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-5">
        <div>
          <label className="block text-xs text-text-muted font-medium mb-1.5">
            Batch Name
          </label>
          <input
            type="text"
            value={batchName}
            onChange={(e) => onBatchNameChange(e.target.value)}
            placeholder="auto-generated from filename"
            className="w-full bg-surface-alt border border-border rounded-md px-3 py-2 text-sm text-text placeholder:text-text-dim focus:outline-none focus:border-accent-cyan"
          />
        </div>
        <div>
          <label className="block text-xs text-text-muted font-medium mb-1.5">
            Owner
          </label>
          <select
            value={ownerId}
            onChange={(e) => onOwnerIdChange(e.target.value)}
            className="w-full bg-surface-alt border border-border rounded-md px-3 py-2 text-sm text-text focus:outline-none focus:border-accent-cyan"
          >
            <option value="">No owner</option>
            {owners.map((o) => (
              <option key={o.id} value={o.id}>{o.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mt-4 bg-red-400/10 border border-red-400/20 rounded-md px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Upload button (CSV only, when file selected) */}
      {source === 'csv' && selectedFile && !isUploading && (
        <div className="mt-5">
          <button
            onClick={handleUpload}
            disabled={!batchName}
            className="bg-accent-cyan text-bg font-semibold px-5 py-2.5 rounded-md hover:opacity-90 transition-opacity text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Upload & Analyze
          </button>
        </div>
      )}
    </div>
  )
}
