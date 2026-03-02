/**
 * MermaidExtension — Custom Tiptap extension for mermaid code blocks.
 *
 * Extends the built-in CodeBlock node to render a custom NodeView when
 * the language attribute is "mermaid". Regular code blocks use the
 * default ProseMirror rendering (NodeViewContent passthrough).
 *
 * This is registered as a replacement for the default codeBlock in StarterKit.
 */

import CodeBlock from '@tiptap/extension-code-block'
import { ReactNodeViewRenderer } from '@tiptap/react'
import { CodeBlockNodeView } from './MermaidBlock'

export const MermaidExtension = CodeBlock.extend({
  // Add language attribute (CodeBlock already has it, but we make
  // sure it's preserved and parsed from markdown fenced blocks)
  addAttributes() {
    return {
      ...this.parent?.(),
      language: {
        default: null,
        parseHTML: (element: HTMLElement) =>
          element.getAttribute('data-language') ||
          element.querySelector('code')?.className?.replace(/^language-/, '') ||
          null,
        renderHTML: (attributes: Record<string, unknown>) => {
          if (!attributes.language) return {}
          return { 'data-language': attributes.language }
        },
      },
    }
  },

  // Use a custom NodeView that renders mermaid blocks as diagrams
  // and regular code blocks as plain pre/code
  addNodeView() {
    return ReactNodeViewRenderer(CodeBlockNodeView)
  },
})
