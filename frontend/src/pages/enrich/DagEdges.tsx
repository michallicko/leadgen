/**
 * DagEdges — SVG overlay drawing Bezier curves between dependent stage cards.
 * Uses refs to card DOM elements to compute connection points.
 * On hover: connected edges jump to foreground (above cards) in cyan.
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
  hoveredStage?: string | null
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

function getBaseStyle(
  edge: Edge,
  mode: DagMode,
  progress: Record<string, StageProgress>,
): { stroke: string; dash: string; opacity: number; width: number } {
  const isSoft = edge.key.includes('~>')
  let stroke: string
  let dash = ''
  let opacity: number
  const width = isSoft ? 1.5 : 2

  if (mode === 'configure') {
    stroke = 'var(--color-text-muted)'
    opacity = 0.5
  } else {
    const fromProgress = progress[edge.from]
    if (!fromProgress) {
      stroke = 'var(--color-text-muted)'
      dash = '4 4'
      opacity = 0.4
    } else if (fromProgress.status === 'completed') {
      stroke = 'var(--color-success)'
      opacity = 0.8
    } else if (fromProgress.status === 'running') {
      stroke = 'var(--color-accent-cyan)'
      dash = '6 3'
      opacity = 0.9
    } else if (fromProgress.status === 'failed') {
      stroke = 'var(--color-error)'
      opacity = 0.7
    } else {
      stroke = 'var(--color-text-muted)'
      dash = '4 4'
      opacity = 0.4
    }
  }

  if (isSoft) dash = '3 3'

  return { stroke, dash, opacity, width }
}

export function DagEdges({
  containerRef,
  cardRefs,
  enabledStages,
  mode,
  progress,
  softDepsConfig,
  hoveredStage = null,
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

  const hasHover = hoveredStage != null

  // Split edges into background (dimmed/normal) and foreground (highlighted)
  const bgEdges: Edge[] = []
  const fgEdges: Edge[] = []

  if (hasHover) {
    for (const edge of edges) {
      if (edge.from === hoveredStage || edge.to === hoveredStage) {
        fgEdges.push(edge)
      } else {
        bgEdges.push(edge)
      }
    }
  } else {
    bgEdges.push(...edges)
  }

  return (
    <>
      {/* Background layer — behind cards (z-0) */}
      <svg
        className="absolute inset-0 pointer-events-none z-0"
        width={size.w}
        height={size.h}
        style={{ overflow: 'visible' }}
      >
        {bgEdges.map((edge) => {
          const { stroke, dash, opacity, width } = getBaseStyle(edge, mode, progress)
          const midY = (edge.y1 + edge.y2) / 2
          return (
            <path
              key={edge.key}
              d={`M ${edge.x1} ${edge.y1} C ${edge.x1} ${midY}, ${edge.x2} ${midY}, ${edge.x2} ${edge.y2}`}
              fill="none"
              stroke={stroke}
              strokeWidth={width}
              strokeDasharray={dash}
              opacity={hasHover ? 0.1 : opacity}
              className="transition-opacity duration-150"
            />
          )
        })}
      </svg>

      {/* Foreground layer — above cards (z-20), only when hovering */}
      {fgEdges.length > 0 && (
        <svg
          className="absolute inset-0 pointer-events-none z-20"
          width={size.w}
          height={size.h}
          style={{ overflow: 'visible' }}
        >
          {fgEdges.map((edge) => {
            const isSoft = edge.key.includes('~>')
            const midY = (edge.y1 + edge.y2) / 2
            return (
              <path
                key={edge.key}
                d={`M ${edge.x1} ${edge.y1} C ${edge.x1} ${midY}, ${edge.x2} ${midY}, ${edge.x2} ${edge.y2}`}
                fill="none"
                stroke="var(--color-accent-cyan)"
                strokeWidth={isSoft ? 2 : 2.5}
                strokeDasharray={isSoft ? '4 4' : ''}
                opacity={1}
              />
            )
          })}
        </svg>
      )}
    </>
  )
}
