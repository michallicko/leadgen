import { useEffect } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Heading from '@tiptap/extension-heading'
import { Table } from '@tiptap/extension-table'
import TableRow from '@tiptap/extension-table-row'
import TableCell from '@tiptap/extension-table-cell'
import TableHeader from '@tiptap/extension-table-header'
import Placeholder from '@tiptap/extension-placeholder'
import { Markdown } from 'tiptap-markdown'
import { STRATEGY_TEMPLATE } from './strategy-template'
import './strategy-editor.css'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface StrategyEditorProps {
  content: string | null
  onUpdate: (content: string) => void
  editable?: boolean
}

// ---------------------------------------------------------------------------
// Toolbar button
// ---------------------------------------------------------------------------

interface ToolbarBtnProps {
  label: string
  active?: boolean
  disabled?: boolean
  onClick: () => void
}

function ToolbarBtn({ label, active, disabled, onClick }: ToolbarBtnProps) {
  return (
    <button
      type="button"
      onMouseDown={(e) => {
        e.preventDefault()
        onClick()
      }}
      disabled={disabled}
      className={`px-2 py-1 text-xs font-medium rounded transition-colors select-none ${
        active
          ? 'bg-accent/20 text-accent-hover'
          : 'text-text-muted hover:text-text hover:bg-surface-alt'
      } ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
    >
      {label}
    </button>
  )
}

function ToolbarDivider() {
  return <div className="w-px h-5 bg-border-solid mx-1 self-center" />
}

// ---------------------------------------------------------------------------
// Toolbar
// ---------------------------------------------------------------------------

interface ToolbarProps {
  editor: ReturnType<typeof useEditor>
}

function Toolbar({ editor }: ToolbarProps) {
  if (!editor) return null

  return (
    <div className="flex flex-wrap items-center gap-0.5 px-3 py-2 border-b border-border-solid bg-surface">
      {/* Inline marks */}
      <ToolbarBtn
        label="B"
        active={editor.isActive('bold')}
        onClick={() => editor.chain().focus().toggleBold().run()}
      />
      <ToolbarBtn
        label="I"
        active={editor.isActive('italic')}
        onClick={() => editor.chain().focus().toggleItalic().run()}
      />

      <ToolbarDivider />

      {/* Headings */}
      <ToolbarBtn
        label="H1"
        active={editor.isActive('heading', { level: 1 })}
        onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
      />
      <ToolbarBtn
        label="H2"
        active={editor.isActive('heading', { level: 2 })}
        onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
      />
      <ToolbarBtn
        label="H3"
        active={editor.isActive('heading', { level: 3 })}
        onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
      />

      <ToolbarDivider />

      {/* Lists */}
      <ToolbarBtn
        label="Bullet"
        active={editor.isActive('bulletList')}
        onClick={() => editor.chain().focus().toggleBulletList().run()}
      />
      <ToolbarBtn
        label="Number"
        active={editor.isActive('orderedList')}
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
      />

      <ToolbarDivider />

      {/* Block elements */}
      <ToolbarBtn
        label="Quote"
        active={editor.isActive('blockquote')}
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
      />
      <ToolbarBtn
        label="Table"
        onClick={() =>
          editor
            .chain()
            .focus()
            .insertTable({ rows: 3, cols: 3, withHeaderRow: true })
            .run()
        }
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// StrategyEditor
// ---------------------------------------------------------------------------

export function StrategyEditor({
  content,
  onUpdate,
  editable = true,
}: StrategyEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: false, // use standalone Heading for level control
      }),
      Heading.configure({
        levels: [1, 2, 3],
      }),
      Table.configure({
        resizable: false,
      }),
      TableRow,
      TableCell,
      TableHeader,
      Placeholder.configure({
        placeholder: 'Start writing your strategy...',
      }),
      Markdown,
    ],
    content: content ?? STRATEGY_TEMPLATE,
    editable,
    onUpdate({ editor: ed }) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      onUpdate((ed.storage as any).markdown.getMarkdown())
    },
  })

  // Sync editable prop changes
  useEffect(() => {
    if (editor) {
      editor.setEditable(editable)
    }
  }, [editor, editable])

  // Sync content prop when it changes (e.g. after research seeds template)
  // Tiptap only uses `content` during initialization, so we must push updates manually.
  useEffect(() => {
    if (editor && content && content.length > 0) {
      // Only update if editor is empty/placeholder — don't overwrite user edits
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const currentMd = (editor.storage as any).markdown?.getMarkdown() || ''
      if (!currentMd || currentMd.trim() === '' || currentMd.includes('Start writing your strategy')) {
        editor.commands.setContent(content)
      }
    }
  }, [editor, content])

  return (
    <div className="strategy-editor rounded-lg border border-border-solid overflow-hidden bg-surface">
      {editable && <Toolbar editor={editor} />}
      <EditorContent editor={editor} />
    </div>
  )
}
