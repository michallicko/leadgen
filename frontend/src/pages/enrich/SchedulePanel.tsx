/**
 * SchedulePanel — manage enrichment schedules linked to saved configs.
 * Appears below the DAG visualization in configure mode.
 */

import { useState } from 'react'
import {
  useEnrichConfigs,
  useEnrichSchedules,
  useSaveSchedule,
  useDeleteSchedule,
  useToggleSchedule,
} from '../../api/queries/useEnrichConfigs'

const CRON_PRESETS = [
  { label: 'Weekly (Mon 2am)', cron: '0 2 * * 1' },
  { label: 'Bi-weekly (1st & 15th)', cron: '0 2 1,15 * *' },
  { label: 'Monthly (1st)', cron: '0 2 1 * *' },
  { label: 'Quarterly', cron: '0 2 1 */3 *' },
]

export function SchedulePanel() {
  const { data: configs } = useEnrichConfigs()
  const { data: schedules, isLoading } = useEnrichSchedules()
  const saveSchedule = useSaveSchedule()
  const deleteSchedule = useDeleteSchedule()
  const toggleSchedule = useToggleSchedule()

  const [isExpanded, setIsExpanded] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [selectedConfig, setSelectedConfig] = useState('')
  const [scheduleType, setScheduleType] = useState<'cron' | 'on_new_entity'>('cron')
  const [cronExpr, setCronExpr] = useState('0 2 * * 1')

  const handleCreate = () => {
    if (!selectedConfig) return
    saveSchedule.mutate(
      {
        config_id: selectedConfig,
        schedule_type: scheduleType,
        cron_expression: scheduleType === 'cron' ? cronExpr : undefined,
      },
      {
        onSuccess: () => {
          setShowCreate(false)
          setSelectedConfig('')
        },
      },
    )
  }

  const activeCount = schedules?.filter((s) => s.is_active).length ?? 0

  return (
    <div className="mt-6 border border-border rounded-lg bg-surface overflow-hidden">
      {/* Header — always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-surface-alt transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text">Schedules</span>
          {activeCount > 0 && (
            <span className="text-[0.65rem] bg-accent/10 text-accent px-1.5 py-0.5 rounded-full">
              {activeCount} active
            </span>
          )}
        </div>
        <span className={`text-text-muted transition-transform ${isExpanded ? 'rotate-180' : ''}`}>
          &#9660;
        </span>
      </button>

      {isExpanded && (
        <div className="border-t border-border px-4 py-3">
          {/* Create new schedule */}
          {!showCreate ? (
            <button
              onClick={() => setShowCreate(true)}
              disabled={!configs || configs.length === 0}
              className="text-sm text-accent hover:text-accent/80 disabled:text-text-dim disabled:cursor-not-allowed"
            >
              + Add schedule...
            </button>
          ) : (
            <div className="space-y-3 p-3 bg-surface-alt rounded-md mb-3">
              {/* Config selector */}
              <div>
                <label className="text-xs text-text-muted block mb-1">Pipeline config</label>
                <select
                  value={selectedConfig}
                  onChange={(e) => setSelectedConfig(e.target.value)}
                  className="w-full text-sm px-2 py-1.5 rounded border border-border bg-surface text-text"
                >
                  <option value="">Select a saved config...</option>
                  {configs?.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>

              {/* Schedule type */}
              <div>
                <label className="text-xs text-text-muted block mb-1">Trigger type</label>
                <div className="flex gap-2">
                  <button
                    onClick={() => setScheduleType('cron')}
                    className={`flex-1 px-3 py-1.5 text-sm rounded border transition-colors ${
                      scheduleType === 'cron'
                        ? 'border-accent bg-accent/10 text-accent'
                        : 'border-border text-text-muted hover:border-accent/40'
                    }`}
                  >
                    Recurring
                  </button>
                  <button
                    onClick={() => setScheduleType('on_new_entity')}
                    className={`flex-1 px-3 py-1.5 text-sm rounded border transition-colors ${
                      scheduleType === 'on_new_entity'
                        ? 'border-accent bg-accent/10 text-accent'
                        : 'border-border text-text-muted hover:border-accent/40'
                    }`}
                  >
                    On new import
                  </button>
                </div>
              </div>

              {/* Cron presets */}
              {scheduleType === 'cron' && (
                <div>
                  <label className="text-xs text-text-muted block mb-1">Frequency</label>
                  <div className="flex flex-wrap gap-1.5">
                    {CRON_PRESETS.map((p) => (
                      <button
                        key={p.cron}
                        onClick={() => setCronExpr(p.cron)}
                        className={`px-2 py-1 text-xs rounded border transition-colors ${
                          cronExpr === p.cron
                            ? 'border-accent bg-accent/10 text-accent'
                            : 'border-border text-text-muted hover:border-accent/40'
                        }`}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                  <input
                    type="text"
                    value={cronExpr}
                    onChange={(e) => setCronExpr(e.target.value)}
                    placeholder="Custom cron expression"
                    className="mt-1.5 w-full px-2 py-1 text-xs rounded border border-border bg-surface text-text font-mono"
                  />
                </div>
              )}

              {/* Actions */}
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => setShowCreate(false)}
                  className="px-3 py-1 text-xs text-text-muted hover:text-text"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreate}
                  disabled={!selectedConfig || saveSchedule.isPending}
                  className="px-3 py-1 text-xs bg-accent text-white rounded disabled:opacity-40"
                >
                  {saveSchedule.isPending ? 'Creating...' : 'Create Schedule'}
                </button>
              </div>
            </div>
          )}

          {/* Existing schedules */}
          {isLoading && <p className="text-xs text-text-dim mt-2">Loading...</p>}
          {!isLoading && schedules && schedules.length > 0 && (
            <div className="mt-3 space-y-2">
              {schedules.map((sched) => {
                const configName = configs?.find((c) => c.id === sched.config_id)?.name ?? 'Unknown'
                const cronLabel = CRON_PRESETS.find((p) => p.cron === sched.cron_expression)?.label
                return (
                  <div
                    key={sched.id}
                    className="flex items-center justify-between px-3 py-2 rounded border border-border bg-surface group"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${sched.is_active ? 'bg-success' : 'bg-border-solid'}`} />
                        <span className="text-sm text-text font-medium">{configName}</span>
                        <span className="text-[0.65rem] text-text-dim">
                          {sched.schedule_type === 'on_new_entity'
                            ? 'On new import'
                            : cronLabel ?? sched.cron_expression}
                        </span>
                      </div>
                      {sched.last_run_at && (
                        <p className="text-[0.6rem] text-text-dim ml-4">
                          Last run: {new Date(sched.last_run_at).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => toggleSchedule.mutate({ id: sched.id, is_active: !sched.is_active })}
                        className={`text-xs ${sched.is_active ? 'text-text-muted hover:text-error' : 'text-text-dim hover:text-success'}`}
                      >
                        {sched.is_active ? 'Pause' : 'Resume'}
                      </button>
                      <button
                        onClick={() => deleteSchedule.mutate(sched.id)}
                        className="text-xs text-text-muted hover:text-error"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
          {!isLoading && (!schedules || schedules.length === 0) && !showCreate && (
            <p className="text-xs text-text-dim mt-2">No schedules configured. Save a pipeline config first, then create a schedule.</p>
          )}
        </div>
      )}
    </div>
  )
}
