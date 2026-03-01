import { useCallback, useMemo, useState } from 'react'
import {
  useUpdateCampaign,
  useCampaignTemplates,
  type CampaignDetail,
  type TemplateStep,
} from '../../../api/queries/useCampaigns'
import {
  useCostEstimate,
  useStartGeneration,
  type CostEstimateResponse,
} from '../../../api/queries/useCampaignGeneration'
import { useToast } from '../../../components/ui/Toast'
import { Modal } from '../../../components/ui/Modal'
import { GenerationProgressModal } from '../../../components/campaign/GenerationProgressModal'
import { EditableSelect, EditableTextarea, FieldGrid, Field } from '../../../components/ui/DetailField'
import { WarningBanner } from '../../../components/ui/WarningBanner'

const TONE_OPTIONS = [
  { value: 'professional', label: 'Professional' },
  { value: 'casual', label: 'Casual' },
  { value: 'bold', label: 'Bold' },
  { value: 'empathetic', label: 'Empathetic' },
]

const CHANNEL_ICONS: Record<string, string> = {
  linkedin_connect: 'LI',
  linkedin_message: 'LI',
  email: 'Em',
  call: 'Ph',
}

interface Props {
  campaign: CampaignDetail
  isEditable: boolean
}

export function MessageGenTab({ campaign, isEditable }: Props) {
  const { toast } = useToast()
  const updateCampaign = useUpdateCampaign()
  const { data: templateData } = useCampaignTemplates()
  const costEstimate = useCostEstimate()
  const startGeneration = useStartGeneration()

  // Cost confirm dialog state
  const [showCostDialog, setShowCostDialog] = useState(false)
  const [costData, setCostData] = useState<CostEstimateResponse | null>(null)
  const [skipUnenriched, setSkipUnenriched] = useState(false)

  // Progress modal state
  const [showProgress, setShowProgress] = useState(false)

  // If campaign is currently generating, show progress modal automatically
  const isGenerating = campaign.status === 'Generating'

  const templates = useMemo(() => templateData?.templates ?? [], [templateData])

  const templateConfig: TemplateStep[] = useMemo(() => {
    return (campaign.template_config || []) as TemplateStep[]
  }, [campaign.template_config])

  const generationConfig = useMemo(() => {
    return (campaign.generation_config || {}) as Record<string, unknown>
  }, [campaign.generation_config])

  const enabledSteps = useMemo(
    () => templateConfig.filter((s) => s.enabled),
    [templateConfig],
  )

  const canGenerate =
    (campaign.status === 'Ready' || campaign.status === 'Draft') &&
    campaign.total_contacts > 0 &&
    enabledSteps.length > 0

  const handleLoadTemplate = useCallback(async (templateId: string) => {
    const tpl = templates.find((t) => t.id === templateId)
    if (!tpl) return
    try {
      await updateCampaign.mutateAsync({
        id: campaign.id,
        data: {
          template_config: tpl.steps,
          generation_config: tpl.default_config,
        },
      })
      toast('Template loaded', 'success')
    } catch {
      toast('Failed to load template', 'error')
    }
  }, [templates, campaign.id, updateCampaign, toast])

  const handleToggleStep = useCallback(async (stepIndex: number) => {
    const newConfig = [...templateConfig]
    newConfig[stepIndex] = { ...newConfig[stepIndex], enabled: !newConfig[stepIndex].enabled }
    try {
      await updateCampaign.mutateAsync({
        id: campaign.id,
        data: { template_config: newConfig },
      })
    } catch {
      toast('Failed to update step', 'error')
    }
  }, [templateConfig, campaign.id, updateCampaign, toast])

  const handleToneChange = useCallback(async (_: string, value: string) => {
    const newConfig = { ...generationConfig, tone: value }
    try {
      await updateCampaign.mutateAsync({
        id: campaign.id,
        data: { generation_config: newConfig },
      })
    } catch {
      toast('Failed to update tone', 'error')
    }
  }, [generationConfig, campaign.id, updateCampaign, toast])

  const handleInstructionsChange = useCallback(async (_: string, value: string) => {
    const newConfig = { ...generationConfig, custom_instructions: value }
    try {
      await updateCampaign.mutateAsync({
        id: campaign.id,
        data: { generation_config: newConfig },
      })
    } catch {
      toast('Failed to update instructions', 'error')
    }
  }, [generationConfig, campaign.id, updateCampaign, toast])

  // Cost estimate -> confirmation dialog
  const handleEstimateCost = useCallback(async () => {
    try {
      const data = await costEstimate.mutateAsync(campaign.id)
      setCostData(data)
      setSkipUnenriched(false)
      setShowCostDialog(true)
    } catch {
      toast('Failed to estimate cost', 'error')
    }
  }, [campaign.id, costEstimate, toast])

  // Confirm generation
  const handleConfirmGenerate = useCallback(async () => {
    setShowCostDialog(false)
    try {
      await startGeneration.mutateAsync({ campaignId: campaign.id, skipUnenriched })
      setShowProgress(true)
    } catch {
      toast('Failed to start generation', 'error')
    }
  }, [campaign.id, startGeneration, toast, skipUnenriched])

  const gaps = costData?.enrichment_gaps

  return (
    <div className="space-y-4">
      {/* Template loader (draft/ready only) */}
      {isEditable && templates.length > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted">Load template:</span>
          {templates.map((t) => (
            <button
              key={t.id}
              onClick={() => handleLoadTemplate(t.id)}
              className="px-2 py-0.5 text-xs rounded border border-border bg-surface text-text-muted hover:text-text hover:border-accent cursor-pointer transition-colors"
            >
              {t.name}
            </button>
          ))}
        </div>
      )}

      {/* Step list */}
      {templateConfig.length > 0 ? (
        <div className="space-y-1.5">
          {templateConfig.map((step, idx) => (
            <div
              key={idx}
              className={`flex items-center gap-3 px-3 py-2 rounded border transition-colors ${
                step.enabled
                  ? 'border-border bg-surface'
                  : 'border-border/50 bg-surface/50 opacity-50'
              }`}
            >
              {isEditable && (
                <button
                  onClick={() => handleToggleStep(idx)}
                  className={`w-4 h-4 rounded border flex items-center justify-center text-[10px] cursor-pointer transition-colors ${
                    step.enabled
                      ? 'bg-accent border-accent text-white'
                      : 'bg-transparent border-[#8B92A0]/40 text-transparent'
                  }`}
                >
                  {step.enabled ? '\u2713' : ''}
                </button>
              )}
              <span className="w-6 h-5 flex items-center justify-center text-[9px] font-bold text-text-muted bg-surface-alt rounded">
                {CHANNEL_ICONS[step.channel] || '?'}
              </span>
              <span className="text-sm text-text flex-1">{step.label}</span>
              <span className="text-xs text-text-dim">{step.channel.replace('_', ' ')}</span>
              {step.needs_pdf && (
                <span className="text-[10px] px-1.5 py-0.5 bg-accent/10 text-accent rounded">PDF</span>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-text-muted">No message steps configured. Load a template above to get started.</p>
      )}

      {/* Generation config (tone + instructions) */}
      {templateConfig.length > 0 && (
        <div className="space-y-3 mt-4">
          {isEditable ? (
            <>
              <EditableSelect
                label="Tone"
                name="tone"
                value={(generationConfig.tone as string) || 'professional'}
                options={TONE_OPTIONS}
                onChange={handleToneChange}
              />
              <EditableTextarea
                label="Custom Instructions"
                name="custom_instructions"
                value={(generationConfig.custom_instructions as string) || ''}
                onChange={handleInstructionsChange}
                rows={3}
                maxLength={2000}
                placeholder="e.g., Mention our Series A funding. Reference prospect's recent company news. Keep under 100 words."
                helpText="These instructions are appended to every message generation prompt for this campaign."
              />
            </>
          ) : (
            <FieldGrid>
              <Field label="Tone" value={(generationConfig.tone as string) || 'professional'} />
              <Field label="Custom Instructions" value={(generationConfig.custom_instructions as string) || '-'} />
            </FieldGrid>
          )}
        </div>
      )}

      {/* Generate actions */}
      {templateConfig.length > 0 && (
        <div className="flex items-center gap-3 pt-4 border-t border-border">
          {canGenerate && (
            <>
              <button
                onClick={handleEstimateCost}
                disabled={costEstimate.isPending}
                className="px-4 py-2 text-sm font-medium rounded border border-border text-text-muted hover:text-text hover:border-accent-cyan cursor-pointer bg-transparent transition-colors disabled:opacity-50"
              >
                {costEstimate.isPending ? 'Estimating...' : 'Estimate Cost'}
              </button>
              <button
                onClick={handleEstimateCost}
                disabled={startGeneration.isPending || costEstimate.isPending}
                className="px-4 py-2 text-sm font-medium rounded bg-accent text-white border-none cursor-pointer hover:bg-accent-hover transition-colors disabled:opacity-50"
              >
                {startGeneration.isPending ? 'Starting...' : 'Generate Messages'}
              </button>
            </>
          )}
          {isGenerating && (
            <button
              onClick={() => setShowProgress(true)}
              className="px-4 py-2 text-sm font-medium rounded border border-accent/30 text-accent-hover bg-accent/10 cursor-pointer hover:bg-accent/20 transition-colors"
            >
              View Progress
            </button>
          )}
          {!canGenerate && !isGenerating && campaign.total_contacts === 0 && (
            <p className="text-xs text-text-dim">Add contacts to the campaign before generating messages.</p>
          )}
          {!canGenerate && !isGenerating && campaign.total_contacts > 0 && enabledSteps.length === 0 && (
            <p className="text-xs text-text-dim">Enable at least one message step to generate.</p>
          )}
        </div>
      )}

      {/* Cost confirmation dialog */}
      <Modal
        open={showCostDialog}
        onClose={() => setShowCostDialog(false)}
        title="Confirm Generation"
        actions={
          <>
            <button
              onClick={() => setShowCostDialog(false)}
              className="px-3 py-1.5 text-sm rounded border border-border text-text-muted hover:text-text cursor-pointer bg-transparent transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirmGenerate}
              disabled={startGeneration.isPending}
              className="px-4 py-1.5 text-sm font-medium rounded bg-accent text-white border-none cursor-pointer hover:bg-accent-hover transition-colors disabled:opacity-50"
            >
              {startGeneration.isPending ? 'Starting...' : 'Generate'}
            </button>
          </>
        }
      >
        {costData && (
          <div className="space-y-4">
            <p className="text-sm text-text">
              Generate{' '}
              <span className="font-semibold text-accent-cyan">{costData.total_messages} messages</span>
              {' '}for{' '}
              <span className="font-semibold text-accent-cyan">{costData.total_contacts} contacts</span>?
            </p>

            {/* Enrichment gap warning */}
            {gaps && gaps.unenriched_contacts > 0 && (
              <div className="space-y-2">
                <WarningBanner
                  variant="warning"
                  message={
                    <span>
                      <strong>{gaps.unenriched_contacts}</strong> of {gaps.total_contacts} contacts
                      have not been fully enriched. Messages for these contacts may be lower quality.
                    </span>
                  }
                />
                <label className="flex items-center gap-2 text-xs text-text-muted cursor-pointer">
                  <input
                    type="checkbox"
                    checked={skipUnenriched}
                    onChange={(e) => setSkipUnenriched(e.target.checked)}
                    className="rounded border-border accent-accent"
                  />
                  Skip unenriched contacts ({gaps.enriched_contacts} of {gaps.total_contacts} will be generated)
                </label>
              </div>
            )}

            {/* Step breakdown */}
            {costData.by_step && costData.by_step.length > 0 && (
              <div className="space-y-1">
                {costData.by_step.map((step) => (
                  <div key={step.step} className="flex items-center justify-between text-xs">
                    <span className="text-text-muted">
                      Step {step.step}: {step.label}
                      <span className="text-text-dim ml-1">({step.channel.replace('_', ' ')})</span>
                    </span>
                    <span className="text-text-dim">{step.count} msgs</span>
                  </div>
                ))}
              </div>
            )}

            {/* Estimated cost */}
            <div className="flex items-center justify-between px-4 py-3 bg-surface-alt rounded-lg border border-border">
              <span className="text-sm text-text-muted">Estimated cost</span>
              <span className="text-lg font-semibold text-accent-cyan">
                ${costData.estimated_cost.toFixed(2)}
              </span>
            </div>
          </div>
        )}
      </Modal>

      {/* Generation progress modal */}
      <GenerationProgressModal
        campaignId={campaign.id}
        isOpen={showProgress || isGenerating}
        onClose={() => setShowProgress(false)}
      />
    </div>
  )
}
