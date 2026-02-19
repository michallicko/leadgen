/**
 * DagVisualization — renders stage cards in labeled rows matching the DAG structure.
 * Row 0: Profiling, Row 1: Company Intelligence, Row 2: Contact Intelligence, Row 3: Validation
 */

import { type ReactNode } from 'react'
import { getStagesByRow } from './stageConfig'

interface DagVisualizationProps {
  children: (stageCode: string, rowIdx: number) => ReactNode
}

export function DagVisualization({ children }: DagVisualizationProps) {
  const rows = getStagesByRow()

  return (
    <div className="relative z-10 flex flex-col gap-8">
      {rows.map((row, rowIdx) => {
        // Skip empty rows
        if (row.stages.length === 0) return null

        return (
          <div key={row.label}>
            {/* Row label */}
            <div className="text-[0.65rem] uppercase tracking-wider text-text-dim font-semibold mb-3">
              {row.label}
            </div>

            {/* Stage cards */}
            <div className="flex flex-wrap gap-4">
              {row.stages.map((stage) => children(stage.code, rowIdx))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
