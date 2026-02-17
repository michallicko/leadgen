/**
 * RichText — renders plain text with light markdown-like formatting.
 *
 * Supports:
 *   **bold**
 *   Numbered lists (lines starting with  1. 2. …)
 *   Bullet lists (lines starting with - or *)
 *   Paragraph breaks (double newline)
 */

interface RichTextProps {
  text: string
  className?: string
}

export function RichText({ text, className = '' }: RichTextProps) {
  if (!text) return null

  const paragraphs = text.split(/\n{2,}/)

  return (
    <div className={`space-y-4 ${className}`}>
      {paragraphs.map((para, pi) => (
        <RichParagraph key={pi} text={para.trim()} />
      ))}
    </div>
  )
}

/* ---- Internal helpers ---- */

function RichParagraph({ text }: { text: string }) {
  if (!text) return null

  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean)

  // Detect list: all lines start with a list marker
  const isNumbered = lines.every((l) => /^\d+[.)]\s/.test(l))
  const isBullet = lines.every((l) => /^[-*]\s/.test(l))

  if (isNumbered) {
    return (
      <ol className="list-decimal list-outside ml-5 space-y-1.5 text-sm text-text leading-relaxed">
        {lines.map((l, i) => (
          <li key={i}><InlineFormat text={l.replace(/^\d+[.)]\s*/, '')} /></li>
        ))}
      </ol>
    )
  }

  if (isBullet) {
    return (
      <ul className="list-disc list-outside ml-5 space-y-1.5 text-sm text-text leading-relaxed">
        {lines.map((l, i) => (
          <li key={i}><InlineFormat text={l.replace(/^[-*]\s*/, '')} /></li>
        ))}
      </ul>
    )
  }

  // Mixed content — join lines, render as paragraph
  return (
    <p className="text-sm text-text leading-relaxed">
      <InlineFormat text={lines.join(' ')} />
    </p>
  )
}

/** Renders **bold** markers as <strong> */
function InlineFormat({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/)

  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={i} className="font-semibold text-text">{part.slice(2, -2)}</strong>
        }
        return <span key={i}>{part}</span>
      })}
    </>
  )
}
