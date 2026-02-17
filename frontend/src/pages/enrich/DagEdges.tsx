/**
 * DagEdges — SVG overlay drawing Bezier curves between dependent stage cards.
 * Uses refs to card DOM elements to compute connection points.
 */

import { useEffect, useState, useCallback } from 'react'
import { STAGES } from './stageConfig'
import type { StageProgress, DagMode } from './StageCard.types'

interface DagEdgesProps {
  containerRef: React.RefObject<HTMLDivElement | null>
  cardRefs: Record<string, HTMLDivElement | null>
  enabledStages: Record<string, boolean>
  mode: DagMode
  progress: Record<string, StageProgress>
  softDepsConfig: Record<string, boolean>
}

interface Edge {
  key: string
  from: string
  to: string
  x1: number
  y1: number
  x2: number
  y2: number
}

function getEdgeColor(
  fromCode: string,
  mode: DagMode,
  progress: Record<string, StageProgress>,
): { stroke: string; dash: string; opacity: number } {
  if (mode === 'configure') {
    return { stroke: 'var(--color-border-solid)', dash: '', opacity: 0.4 }
  }

  const fromProgress = progress[fromCode]
  if (!fromProgress) {
    return { stroke: 'var(--color-border-solid)', dash: '4 4', opacity: 0.3 }
  }

  if (fromProgress.status === 'completed') {
    return { stroke: 'var(--color-success)', dash: '', opacity: 0.6 }
  }
  if (fromProgress.status === 'running') {
    return { stroke: 'var(--color-accent-cyan)', dash: '6 3', opacity: 0.8 }
  }
  if (fromProgress.status === 'failed') {
    return { stroke: 'var(--color-error)', dash: '', opacity: 0.5 }
  }
  return { stroke: 'var(--color-border-solid)', dash: '4 4', opacity: 0.3 }
}

export function DagEdges({
  containerRef,
  cardRefs,
  enabledStages,
  mode,
  progress,
  softDepsConfig,
}: DagEdgesProps) {
  const [edges, setEdges] = useState<Edge[]>([])
  const [size, setSize] = useState({ w: 0, h: 0 })

  const computeEdges = useCallback(() => {
    const container = containerRef.current
    if (!container) return

    const containerRect = container.getBoundingClientRect()
    setSize({ w: containerRect.width, h: containerRect.height })

    const newEdges: Edge[] = []

    for (const stage of STAGES) {
      if (!enabledStages[stage.code]) continue

      const toEl = cardRefs[stage.code]
      if (!toEl) continue

      // Hard deps
      for (const dep of stage.hardDeps) {
        if (!enabledStages[dep]) continue
        const fromEl = cardRefs[dep]
        if (!fromEl) continue

        const fromRect = fromEl.getBoundingClientRect()
        const toRect = toEl.getBoundingClientRect()

        newEdges.push({
          key: `${dep}->${stage.code}`,
          from: dep,
          to: stage.code,
          x1: fromRect.left + fromRect.width / 2 - containerRect.left,
          y1: fromRect.bottom - containerRect.top,
          x2: toRect.left + toRect.width / 2 - containerRect.left,
          y2: toRect.top - containerRect.top,
        })
      }

      // Soft deps (only if active)
      for (const dep of stage.softDeps) {
        const sdKey = `${stage.code}:${dep}`
        if (softDepsConfig[sdKey] === false) continue
        if (!enabledStages[dep]) continue

        const fromEl = cardRefs[dep]
        if (!fromEl) continue

        const fromRect = fromEl.getBoundingClientRect()
        const toRect = toEl.getBoundingClientRect()

        newEdges.push({
          key: `${dep}~>${stage.code}`,
          from: dep,
          to: stage.code,
          x1: fromRect.left + fromRect.width / 2 - containerRect.left,
          y1: fromRect.bottom - containerRect.top,
          x2: toRect.left + toRect.width / 2 - containerRect.left,
          y2: toRect.top - containerRect.top,
        })
      }
    }

    setEdges(newEdges)
  }, [containerRef, cardRefs, enabledStages, softDepsConfig])

  // Recompute on mount, mode change, stage toggle, and resize
  useEffect(() => {
    computeEdges()

    const handleResize = () => computeEdges()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [computeEdges, mode])

  // Recompute when card refs change (estimates load = cards resize)
  useEffect(() => {
    const timer = setTimeout(computeEdges, 100)
    return () => clearTimeout(timer)
  }, [computeEdges, progress])

  if (edges.length === 0) return null

  return (
    <svg
      className="absolute inset-0 pointer-events-none"
      width={size.w}
      height={size.h}
      style={{ overflow: 'visible' }}
    >
      {edges.map((edge) => {
        const { stroke, dash, opacity } = getEdgeColor(edge.from, mode, progress)
        const isSoft = edge.key.includes('~>')
        const midY = (edge.y1 + edge.y2) / 2

        return (
          <path
            key={edge.key}
            d={`M ${edge.x1} ${edge.y1} C ${edge.x1} ${midY}, ${edge.x2} ${midY}, ${edge.x2} ${edge.y2}`}
            fill="none"
            stroke={stroke}
            strokeWidth={isSoft ? 1 : 1.5}
            strokeDasharray={isSoft ? '3 3' : dash}
            opacity={opacity}
          />
        )
      })}
    </svg>
  )
}
