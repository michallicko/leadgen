import { useCallback, useMemo } from 'react'
import {
  useUpdateCampaign,
  useCampaignTemplates,
  type CampaignDetail,
  type TemplateStep,
} from '../../../api/queries/useCampaigns'
import { useToast } from '../../../components/ui/Toast'
import { EditableSelect, EditableTextarea, FieldGrid, Field } from '../../../components/ui/DetailField'

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

  const templates = useMemo(() => templateData?.templates ?? [], [templateData])

  const templateConfig: TemplateStep[] = useMemo(() => {
    return (campaign.template_config || []) as TemplateStep[]
  }, [campaign.template_config])

  const generationConfig = useMemo(() => {
    return (campaign.generation_config || {}) as Record<string, unknown>
  }, [campaign.generation_config])

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
    </div>
  )
}
