/**
 * QualityScore -- AI quality scoring display for strategy sections.
 *
 * Shows:
 * - Overall quality badge with score (1-5)
 * - "Score Strategy" button to trigger AI evaluation
 * - Per-section scores in an expandable panel
 * - Color coding: green (4+), yellow (3-4), red (<3)
 *
 * Layer 2 of the two-layer quality scoring system (BL-1016).
 */

import { useState } from 'react'
import type { SectionScoreResult } from '../../api/queries/usePlaybook'

interface QualityScoreProps {
  scores: SectionScoreResult[]
  overallQuality: number | null
  overallAssessment: string
  isLoading: boolean
  onRequestScore: () => void
}

function scoreColor(score: number): string {
  if (score >= 4) return 'var(--color-success, #22c55e)'
  if (score >= 3) return 'var(--color-warning, #f59e0b)'
  return 'var(--color-error, #ef4444)'
}

function scoreBgClass(score: number): string {
  if (score >= 4) return 'bg-green-50 text-green-700 border-green-200'
  if (score >= 3) return 'bg-yellow-50 text-yellow-700 border-yellow-200'
  return 'bg-red-50 text-red-700 border-red-200'
}

function ScoreBadge({ score }: { score: number }) {
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 text-xs font-semibold rounded border ${scoreBgClass(score)}`}
    >
      {score.toFixed(1)}
    </span>
  )
}

function SectionDetail({ section }: { section: SectionScoreResult }) {
  const [expanded, setExpanded] = useState(false)

  if (section.quality_score === null) {
    return null
  }

  return (
    <div className="border-b border-border-solid last:border-b-0">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-surface-alt transition-colors"
      >
        <span className="text-xs text-text truncate mr-2">{section.section_name}</span>
        <ScoreBadge score={section.quality_score} />
      </button>

      {expanded && (
        <div className="px-3 pb-2 space-y-1">
          {section.quality_reasoning && (
            <p className="text-xs text-text-muted">{section.quality_reasoning}</p>
          )}
          {section.improvement_suggestions.length > 0 && (
            <ul className="text-xs text-text-muted list-disc list-inside space-y-0.5">
              {section.improvement_suggestions.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

export function QualityScore({
  scores,
  overallQuality,
  overallAssessment,
  isLoading,
  onRequestScore,
}: QualityScoreProps) {
  const [showDetails, setShowDetails] = useState(false)
  const hasScores = overallQuality !== null

  return (
    <div className="flex items-center gap-2 px-3 py-1.5">
      {/* Score button / badge */}
      {hasScores ? (
        <button
          type="button"
          onClick={() => setShowDetails(!showDetails)}
          className="flex items-center gap-1.5 text-xs hover:opacity-80 transition-opacity"
          title={overallAssessment || 'Click to see details'}
        >
          <span className="text-text-muted">Quality:</span>
          <span
            className="font-semibold"
            style={{ color: scoreColor(overallQuality!) }}
          >
            {overallQuality!.toFixed(1)}/5
          </span>
        </button>
      ) : (
        <button
          type="button"
          onClick={onRequestScore}
          disabled={isLoading}
          className="flex items-center gap-1 px-2 py-1 text-xs font-medium rounded
            bg-surface-alt text-text-muted hover:text-text hover:bg-surface
            border border-border-solid transition-colors
            disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <>
              <span className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
              Scoring...
            </>
          ) : (
            'Score Strategy'
          )}
        </button>
      )}

      {/* Re-score button when scores exist */}
      {hasScores && (
        <button
          type="button"
          onClick={onRequestScore}
          disabled={isLoading}
          className="text-xs text-text-muted hover:text-text transition-colors disabled:opacity-50"
          title="Re-score strategy"
        >
          {isLoading ? (
            <span className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
          ) : (
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M1 4v6h6" />
              <path d="M3.51 10a7 7 0 0 0 12.13-3.5" />
              <path d="M15 12V6H9" />
              <path d="M12.49 6A7 7 0 0 0 .36 9.5" />
            </svg>
          )}
        </button>
      )}

      {/* Details panel (shown as dropdown) */}
      {showDetails && hasScores && (
        <div className="absolute right-0 top-full mt-1 z-50 w-80 bg-surface border border-border-solid rounded-lg shadow-lg overflow-hidden">
          {/* Overall assessment */}
          {overallAssessment && (
            <div className="px-3 py-2 bg-surface-alt border-b border-border-solid">
              <p className="text-xs text-text-muted">{overallAssessment}</p>
            </div>
          )}

          {/* Per-section scores */}
          <div className="max-h-64 overflow-y-auto">
            {scores
              .filter((s) => s.quality_score !== null)
              .map((section) => (
                <SectionDetail key={section.section_name} section={section} />
              ))}
          </div>
        </div>
      )}
    </div>
  )
}
