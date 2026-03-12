import { useState, useCallback } from 'react'
import {
  useCampaignSteps,
  useAddCampaignStep,
  useUpdateCampaignStep,
  useDeleteCampaignStep,
  useReorderCampaignSteps,
  usePopulateFromTemplate,
  type CampaignStep,
  type StepConfig,
  type ExampleMessage,
} from '../../../api/queries/useCampaignSteps'
import { useCampaignTemplates } from '../../../api/queries/useCampaigns'
import { useToast } from '../../../components/ui/Toast'
import { SectionDivider } from '../../../components/ui/DetailField'

// ── Constants ────────────────────────────────────────────

const CHANNEL_OPTIONS = [
  { value: 'linkedin_connect', label: 'LinkedIn Connect' },
  { value: 'linkedin_message', label: 'LinkedIn Message' },
  { value: 'email', label: 'Email' },
  { value: 'call', label: 'Call Script' },
]

const CHANNEL_MAX_LENGTH: Record<string, number> = {
  linkedin_connect: 300,
  linkedin_message: 1900,
  email: 5000,
  call: 2000,
}

const CHANNEL_ICONS: Record<string, string> = {
  linkedin_connect: 'LI',
  linkedin_message: 'LI',
  email: 'Em',
  call: 'Ph',
}

const TONE_OPTIONS = [
  { value: 'professional', label: 'Professional' },
  { value: 'casual', label: 'Casual' },
  { value: 'bold', label: 'Bold' },
  { value: 'empathetic', label: 'Empathetic' },
]

// ── Props ────────────────────────────────────────────────

interface Props {
  campaignId: string
  isEditable: boolean
}

// ── StepsTab ─────────────────────────────────────────────

export function StepsTab({ campaignId, isEditable }: Props) {
  const { toast } = useToast()
  const { data, isLoading } = useCampaignSteps(campaignId)
  const { data: templateData } = useCampaignTemplates()
  const addStep = useAddCampaignStep()
  const updateStep = useUpdateCampaignStep()
  const deleteStep = useDeleteCampaignStep()
  const reorderSteps = useReorderCampaignSteps()
  const populateFromTemplate = usePopulateFromTemplate()

  const steps = data?.steps ?? []
  const templates = templateData?.templates ?? []

  // Track which step card is expanded for config editing
  const [expandedId, setExpandedId] = useState<string | null>(null)

  // Template dropdown
  const [selectedTemplateId, setSelectedTemplateId] = useState('')

  const toggleExpand = useCallback((id: string) => {
    setExpandedId((prev) => (prev === id ? null : id))
  }, [])

  // ── Add step ──

  const handleAddStep = useCallback(async () => {
    try {
      const result = await addStep.mutateAsync({
        campaignId,
        data: {
          channel: 'linkedin_message',
          day_offset: 0,
          label: `Step ${steps.length + 1}`,
          config: { max_length: CHANNEL_MAX_LENGTH.linkedin_message, tone: 'professional', language: 'en' },
        },
      })
      setExpandedId(result.id)
      toast('Step added', 'success')
    } catch {
      toast('Failed to add step', 'error')
    }
  }, [campaignId, steps.length, addStep, toast])

  // ── Delete step ──

  const handleDelete = useCallback(async (stepId: string) => {
    try {
      await deleteStep.mutateAsync({ campaignId, stepId })
      if (expandedId === stepId) setExpandedId(null)
      toast('Step deleted', 'success')
    } catch {
      toast('Failed to delete step', 'error')
    }
  }, [campaignId, deleteStep, expandedId, toast])

  // ── Reorder ──

  const handleMoveUp = useCallback(async (index: number) => {
    if (index === 0) return
    const newOrder = steps.map((s) => s.id)
    ;[newOrder[index - 1], newOrder[index]] = [newOrder[index], newOrder[index - 1]]
    try {
      await reorderSteps.mutateAsync({ campaignId, order: newOrder })
    } catch {
      toast('Failed to reorder', 'error')
    }
  }, [campaignId, steps, reorderSteps, toast])

  const handleMoveDown = useCallback(async (index: number) => {
    if (index === steps.length - 1) return
    const newOrder = steps.map((s) => s.id)
    ;[newOrder[index], newOrder[index + 1]] = [newOrder[index + 1], newOrder[index]]
    try {
      await reorderSteps.mutateAsync({ campaignId, order: newOrder })
    } catch {
      toast('Failed to reorder', 'error')
    }
  }, [campaignId, steps, reorderSteps, toast])

  // ── Update step field ──

  const handleUpdateField = useCallback(async (
    step: CampaignStep,
    field: 'channel' | 'day_offset' | 'label' | 'config',
    value: unknown,
  ) => {
    try {
      await updateStep.mutateAsync({
        campaignId,
        stepId: step.id,
        data: { [field]: value },
      })
    } catch {
      toast('Failed to update step', 'error')
    }
  }, [campaignId, updateStep, toast])

  // ── Populate from template ──

  const handlePopulateFromTemplate = useCallback(async () => {
    if (!selectedTemplateId) return
    try {
      await populateFromTemplate.mutateAsync({ campaignId, templateId: selectedTemplateId })
      setSelectedTemplateId('')
      toast('Steps populated from template', 'success')
    } catch {
      toast('Failed to populate from template', 'error')
    }
  }, [campaignId, selectedTemplateId, populateFromTemplate, toast])

  // ── Loading ──

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-6 h-6 border-2 border-border border-t-accent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="max-w-2xl space-y-4">
      {/* From template */}
      {isEditable && templates.length > 0 && (
        <div className="flex items-center gap-2">
          <select
            value={selectedTemplateId}
            onChange={(e) => setSelectedTemplateId(e.target.value)}
            className="px-2 py-1.5 text-xs rounded border border-border bg-surface text-text focus:outline-none focus:border-accent"
          >
            <option value="">Load from template...</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
          <button
            onClick={handlePopulateFromTemplate}
            disabled={!selectedTemplateId || populateFromTemplate.isPending}
            className="px-3 py-1.5 text-xs font-medium rounded border border-border text-text-muted hover:text-text hover:border-accent cursor-pointer bg-transparent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {populateFromTemplate.isPending ? 'Loading...' : 'Apply'}
          </button>
          {steps.length > 0 && (
            <span className="text-[10px] text-warning">Replaces all existing steps</span>
          )}
        </div>
      )}

      {/* Step cards */}
      {steps.length > 0 ? (
        <div className="space-y-2">
          {steps.map((step, idx) => (
            <StepCard
              key={step.id}
              step={step}
              index={idx}
              total={steps.length}
              isEditable={isEditable}
              isExpanded={expandedId === step.id}
              onToggleExpand={() => toggleExpand(step.id)}
              onMoveUp={() => handleMoveUp(idx)}
              onMoveDown={() => handleMoveDown(idx)}
              onDelete={() => handleDelete(step.id)}
              onUpdateField={(field, value) => handleUpdateField(step, field, value)}
            />
          ))}
        </div>
      ) : (
        <p className="text-xs text-text-muted py-4">
          No steps configured. Add steps manually or load from a template.
        </p>
      )}

      {/* Add step button */}
      {isEditable && (
        <button
          onClick={handleAddStep}
          disabled={addStep.isPending}
          className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded border border-dashed border-border text-text-muted hover:text-text hover:border-accent cursor-pointer bg-transparent transition-colors disabled:opacity-50 w-full justify-center"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M7 3v8M3 7h8" />
          </svg>
          {addStep.isPending ? 'Adding...' : 'Add Step'}
        </button>
      )}
    </div>
  )
}

// ── StepCard ─────────────────────────────────────────────

interface StepCardProps {
  step: CampaignStep
  index: number
  total: number
  isEditable: boolean
  isExpanded: boolean
  onToggleExpand: () => void
  onMoveUp: () => void
  onMoveDown: () => void
  onDelete: () => void
  onUpdateField: (field: 'channel' | 'day_offset' | 'label' | 'config', value: unknown) => void
}

function StepCard({
  step,
  index,
  total,
  isEditable,
  isExpanded,
  onToggleExpand,
  onMoveUp,
  onMoveDown,
  onDelete,
  onUpdateField,
}: StepCardProps) {
  const config = step.config || {}
  const maxLength = config.max_length ?? CHANNEL_MAX_LENGTH[step.channel] ?? 1900
  const channelLabel = CHANNEL_OPTIONS.find((c) => c.value === step.channel)?.label ?? step.channel

  // Config summary line
  const summaryParts: string[] = []
  if (config.tone) summaryParts.push(config.tone)
  if (config.language && config.language !== 'en') summaryParts.push(config.language)
  if (config.max_length) summaryParts.push(`${config.max_length} chars`)
  if (config.example_messages?.length) summaryParts.push(`${config.example_messages.length} example(s)`)

  return (
    <div className="border border-border rounded-lg bg-surface overflow-hidden">
      {/* Collapsed header */}
      <div
        className="flex items-center gap-3 px-3 py-2.5 cursor-pointer hover:bg-surface-alt/50 transition-colors"
        onClick={onToggleExpand}
      >
        {/* Position badge */}
        <span className="w-6 h-6 flex items-center justify-center text-[10px] font-bold text-text-muted bg-surface-alt rounded-md flex-shrink-0">
          {step.position}
        </span>

        {/* Channel icon */}
        <span className="w-6 h-5 flex items-center justify-center text-[9px] font-bold text-text-muted bg-surface-alt rounded flex-shrink-0">
          {CHANNEL_ICONS[step.channel] || '?'}
        </span>

        {/* Label */}
        <span className="text-sm text-text flex-1 truncate">
          {step.label || channelLabel}
        </span>

        {/* Day offset */}
        <span className="text-xs text-text-dim flex-shrink-0">
          Day {step.day_offset}
        </span>

        {/* Config summary */}
        {summaryParts.length > 0 && (
          <span className="text-[10px] text-text-dim flex-shrink-0 hidden sm:inline">
            {summaryParts.join(' / ')}
          </span>
        )}

        {/* Reorder arrows */}
        {isEditable && (
          <div className="flex flex-col gap-0.5 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={onMoveUp}
              disabled={index === 0}
              className="w-5 h-3.5 flex items-center justify-center text-text-dim hover:text-text disabled:opacity-30 bg-transparent border-none cursor-pointer disabled:cursor-not-allowed p-0 transition-colors"
              title="Move up"
            >
              <svg width="10" height="6" viewBox="0 0 10 6" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M1 5l4-4 4 4" />
              </svg>
            </button>
            <button
              onClick={onMoveDown}
              disabled={index === total - 1}
              className="w-5 h-3.5 flex items-center justify-center text-text-dim hover:text-text disabled:opacity-30 bg-transparent border-none cursor-pointer disabled:cursor-not-allowed p-0 transition-colors"
              title="Move down"
            >
              <svg width="10" height="6" viewBox="0 0 10 6" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M1 1l4 4 4-4" />
              </svg>
            </button>
          </div>
        )}

        {/* Expand indicator */}
        <svg
          width="12"
          height="12"
          viewBox="0 0 12 12"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          className={`text-text-dim flex-shrink-0 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
        >
          <path d="M3 4.5l3 3 3-3" />
        </svg>
      </div>

      {/* Expanded config editor */}
      {isExpanded && (
        <div className="px-4 py-4 border-t border-border space-y-4">
          {/* Basic fields */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {/* Channel */}
            <div>
              <label className="text-xs text-text-muted mb-1 block">Channel</label>
              <select
                value={step.channel}
                onChange={(e) => {
                  const ch = e.target.value
                  onUpdateField('channel', ch)
                  // Reset max_length to channel default
                  const newConfig = { ...config, max_length: CHANNEL_MAX_LENGTH[ch] ?? 1900 }
                  onUpdateField('config', newConfig)
                }}
                disabled={!isEditable}
                className="w-full px-2 py-1.5 text-sm rounded border border-border bg-surface-alt text-text focus:outline-none focus:border-accent disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {CHANNEL_OPTIONS.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>

            {/* Day offset */}
            <div>
              <label className="text-xs text-text-muted mb-1 block">Day Offset</label>
              <input
                type="number"
                min={0}
                value={step.day_offset}
                onChange={(e) => onUpdateField('day_offset', parseInt(e.target.value, 10) || 0)}
                disabled={!isEditable}
                className="w-full px-2 py-1.5 text-sm rounded border border-border bg-surface-alt text-text focus:outline-none focus:border-accent disabled:opacity-50 disabled:cursor-not-allowed"
              />
            </div>

            {/* Label */}
            <div>
              <label className="text-xs text-text-muted mb-1 block">Label</label>
              <input
                type="text"
                value={step.label}
                onChange={(e) => onUpdateField('label', e.target.value)}
                disabled={!isEditable}
                placeholder="e.g., Introduction"
                className="w-full px-2 py-1.5 text-sm rounded border border-border bg-surface-alt text-text focus:outline-none focus:border-accent disabled:opacity-50 disabled:cursor-not-allowed"
              />
            </div>
          </div>

          <SectionDivider title="Generation Config" />

          {/* Max length slider */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs text-text-muted">Max Length</label>
              <span className="text-sm font-medium text-text tabular-nums">{maxLength} chars</span>
            </div>
            <input
              type="range"
              min={50}
              max={CHANNEL_MAX_LENGTH[step.channel] ?? 5000}
              step={50}
              value={maxLength}
              onChange={(e) => {
                const newConfig = { ...config, max_length: parseInt(e.target.value, 10) }
                onUpdateField('config', newConfig)
              }}
              disabled={!isEditable}
              className="w-full accent-accent h-1.5 bg-surface-alt rounded-full cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            />
            <div className="flex justify-between text-[10px] text-text-dim mt-0.5">
              <span>50</span>
              <span>{CHANNEL_MAX_LENGTH[step.channel] ?? 5000}</span>
            </div>
          </div>

          {/* Tone and Language */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-text-muted mb-1 block">Tone</label>
              <select
                value={config.tone ?? 'professional'}
                onChange={(e) => {
                  const newConfig = { ...config, tone: e.target.value }
                  onUpdateField('config', newConfig)
                }}
                disabled={!isEditable}
                className="w-full px-2 py-1.5 text-sm rounded border border-border bg-surface-alt text-text focus:outline-none focus:border-accent disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {TONE_OPTIONS.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-text-muted mb-1 block">Language</label>
              <input
                type="text"
                value={config.language ?? 'en'}
                onChange={(e) => {
                  const newConfig = { ...config, language: e.target.value }
                  onUpdateField('config', newConfig)
                }}
                disabled={!isEditable}
                placeholder="en"
                className="w-full px-2 py-1.5 text-sm rounded border border-border bg-surface-alt text-text focus:outline-none focus:border-accent disabled:opacity-50 disabled:cursor-not-allowed"
              />
            </div>
          </div>

          {/* Custom instructions */}
          <div>
            <label className="text-xs text-text-muted mb-1 block">Custom Instructions</label>
            <textarea
              value={config.custom_instructions ?? ''}
              onChange={(e) => {
                const newConfig = { ...config, custom_instructions: e.target.value }
                onUpdateField('config', newConfig)
              }}
              disabled={!isEditable}
              rows={2}
              placeholder="e.g., Reference their recent Series A. Keep it under 3 sentences."
              className="w-full px-2 py-1.5 text-sm rounded border border-border bg-surface-alt text-text focus:outline-none focus:border-accent disabled:opacity-50 disabled:cursor-not-allowed resize-none"
            />
          </div>

          {/* Example messages */}
          <ExampleMessagesEditor
            examples={config.example_messages ?? []}
            isEditable={isEditable}
            onChange={(examples) => {
              const newConfig = { ...config, example_messages: examples }
              onUpdateField('config', newConfig)
            }}
          />

          {/* Delete */}
          {isEditable && (
            <div className="flex justify-end pt-2 border-t border-border">
              <button
                onClick={onDelete}
                className="px-3 py-1.5 text-xs text-error hover:text-error/80 bg-transparent border border-error/20 hover:border-error/40 rounded cursor-pointer transition-colors"
              >
                Delete Step
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── ExampleMessagesEditor ────────────────────────────────

interface ExampleMessagesEditorProps {
  examples: ExampleMessage[]
  isEditable: boolean
  onChange: (examples: ExampleMessage[]) => void
}

function ExampleMessagesEditor({ examples, isEditable, onChange }: ExampleMessagesEditorProps) {
  const handleAdd = () => {
    onChange([...examples, { text: '', note: '' }])
  }

  const handleRemove = (index: number) => {
    onChange(examples.filter((_, i) => i !== index))
  }

  const handleChange = (index: number, field: 'text' | 'note', value: string) => {
    const updated = examples.map((ex, i) => (i === index ? { ...ex, [field]: value } : ex))
    onChange(updated)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="text-xs text-text-muted">Example Messages</label>
        {isEditable && (
          <button
            onClick={handleAdd}
            className="text-[10px] text-accent-cyan hover:text-accent-cyan/80 bg-transparent border-none cursor-pointer transition-colors"
          >
            + Add example
          </button>
        )}
      </div>
      {examples.length > 0 ? (
        <div className="space-y-3">
          {examples.map((ex, idx) => (
            <div key={idx} className="border border-border/50 rounded-md p-2.5 bg-surface-alt/30">
              <div className="flex items-start justify-between gap-2 mb-1.5">
                <span className="text-[10px] text-text-dim font-medium">Example {idx + 1}</span>
                {isEditable && (
                  <button
                    onClick={() => handleRemove(idx)}
                    className="text-[10px] text-error/60 hover:text-error bg-transparent border-none cursor-pointer transition-colors p-0"
                  >
                    Remove
                  </button>
                )}
              </div>
              <textarea
                value={ex.text}
                onChange={(e) => handleChange(idx, 'text', e.target.value)}
                disabled={!isEditable}
                rows={3}
                placeholder="Paste an example message..."
                className="w-full px-2 py-1.5 text-xs rounded border border-border bg-surface text-text focus:outline-none focus:border-accent disabled:opacity-50 disabled:cursor-not-allowed resize-none mb-1.5"
              />
              <input
                type="text"
                value={ex.note ?? ''}
                onChange={(e) => handleChange(idx, 'note', e.target.value)}
                disabled={!isEditable}
                placeholder="Note (e.g., good opening hook)"
                className="w-full px-2 py-1 text-[11px] rounded border border-border bg-surface text-text-muted focus:outline-none focus:border-accent disabled:opacity-50 disabled:cursor-not-allowed"
              />
            </div>
          ))}
        </div>
      ) : (
        <p className="text-[11px] text-text-dim">No examples yet. Add examples to guide the AI tone and style.</p>
      )}
    </div>
  )
}
