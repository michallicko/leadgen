/**
 * AgentEditing — processes DOCUMENT_EDIT events and applies surgical
 * edits to the Tiptap editor.
 *
 * Maps section names to Tiptap node positions by searching for H2
 * headings, then applies insert/replace/delete operations at the
 * correct document positions.
 *
 * Usage:
 *   const { applyEdit, pendingEdits } = useAgentEditing(editor)
 *   // In SSE handler: applyEdit(documentEditEvent)
 */

import { useCallback, useState, useRef } from 'react'
import type { Editor } from '@tiptap/react'
import type { DocumentEditEvent, Suggestion } from '../../types/agui'

/**
 * Find the position range of a section by its H2 heading text.
 *
 * Returns the position right after the heading (start of content)
 * and the position just before the next H2 heading (or end of doc).
 */
function findSectionRange(
  editor: Editor,
  sectionName: string,
): { from: number; to: number } | null {
  const doc = editor.state.doc
  let sectionStart: number | null = null
  let sectionEnd: number | null = null

  doc.descendants((node, pos) => {
    if (node.type.name === 'heading' && node.attrs.level === 2) {
      const headingText = node.textContent.trim().toLowerCase()
      const targetText = sectionName.trim().toLowerCase()

      if (sectionStart !== null && sectionEnd === null) {
        // Found the next H2 after our target section
        sectionEnd = pos
        return false // stop iteration
      }

      if (headingText === targetText || headingText.includes(targetText)) {
        // Found the target heading — content starts after this node
        sectionStart = pos + node.nodeSize
      }
    }
    return true // continue iteration
  })

  if (sectionStart === null) return null

  // If no next H2 found, section extends to end of document
  if (sectionEnd === null) {
    sectionEnd = doc.content.size
  }

  return { from: sectionStart, to: sectionEnd }
}

interface UseAgentEditingReturn {
  /** Apply a document edit event from the agent. */
  applyEdit: (edit: DocumentEditEvent) => void
  /** List of pending edit suggestions (for accept/reject mode). */
  pendingEdits: Suggestion[]
  /** Clear all pending edits. */
  clearPendingEdits: () => void
}

export function useAgentEditing(editor: Editor | null): UseAgentEditingReturn {
  const [pendingEdits, setPendingEdits] = useState<Suggestion[]>([])
  const editCounterRef = useRef(0)

  const applyEdit = useCallback(
    (edit: DocumentEditEvent) => {
      if (!editor) return

      const range = findSectionRange(editor, edit.section)
      if (!range) {
        console.warn(`[AgentEditing] Section "${edit.section}" not found in document`)
        return
      }

      const suggestion: Suggestion = {
        id: edit.editId || `edit-${++editCounterRef.current}`,
        type: edit.operation === 'delete' ? 'delete' : edit.operation === 'replace' ? 'replace' : 'add',
        section: edit.section,
        content: edit.content,
        from: range.from,
        to: range.to,
      }

      switch (edit.operation) {
        case 'insert': {
          const insertPos = edit.position === 'start' ? range.from : range.to
          editor
            .chain()
            .focus()
            .insertContentAt(insertPos, edit.content)
            .run()

          // Track as pending suggestion
          suggestion.from = insertPos
          suggestion.to = insertPos + edit.content.length
          break
        }

        case 'replace': {
          // Store original content for undo
          const originalContent = editor.state.doc.textBetween(range.from, range.to)
          suggestion.originalContent = originalContent

          editor
            .chain()
            .focus()
            .deleteRange({ from: range.from, to: range.to })
            .insertContentAt(range.from, edit.content)
            .run()

          suggestion.to = range.from + edit.content.length
          break
        }

        case 'delete': {
          const deletedContent = editor.state.doc.textBetween(range.from, range.to)
          suggestion.originalContent = deletedContent
          suggestion.content = deletedContent

          editor
            .chain()
            .focus()
            .deleteRange({ from: range.from, to: range.to })
            .run()
          break
        }
      }

      // Add to pending edits for accept/reject tracking
      setPendingEdits((prev) => [...prev, suggestion])
    },
    [editor],
  )

  const clearPendingEdits = useCallback(() => {
    setPendingEdits([])
  }, [])

  return { applyEdit, pendingEdits, clearPendingEdits }
}
