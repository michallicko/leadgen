/**
 * BlockToolbar -- hover toolbar for complex block elements (tables, diagrams).
 *
 * Shows a delete button when hovering over the parent block.
 * The parent must have `relative` + `group` Tailwind classes.
 */

import { useCallback } from 'react'
import type { Editor } from '@tiptap/react'

interface BlockToolbarProps {
  editor: Editor
  nodePos: number
  nodeSize: number
}

export function BlockToolbar({ editor, nodePos, nodeSize }: BlockToolbarProps) {
  const handleDelete = useCallback(() => {
    editor.chain().focus().deleteRange({ from: nodePos, to: nodePos + nodeSize }).run()
  }, [editor, nodePos, nodeSize])

  return (
    <div className="absolute -top-8 right-0 flex items-center gap-1 bg-surface border border-border-solid rounded-md shadow-sm px-1.5 py-0.5 z-20 opacity-0 group-hover:opacity-100 transition-opacity">
      <button
        type="button"
        onClick={handleDelete}
        className="p-1 text-text-muted hover:text-error rounded transition-colors"
        title="Delete block"
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="3 6 5 6 21 6" />
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
        </svg>
      </button>
    </div>
  )
}
