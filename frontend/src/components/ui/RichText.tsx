/**
 * RichText — renders plain text with light markdown-like formatting.
 *
 * Supports:
 *   **bold**
 *   Numbered lists (lines starting with  1. 2. …)
 *   Inline numbered lists (1. text 2. text — split automatically)
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

/**
 * Split inline numbered lists: "1. foo 2. bar 3. baz" → ["1. foo", "2. bar", "3. baz"]
 * Only triggers when we detect "N. " patterns mid-text (not just at start).
 */
function splitInlineNumbers(text: string): string[] {
  // Check if there are inline numbers (e.g. ". 2. " pattern mid-text)
  if (!/\.\s+\d+[.)]\s/.test(text)) return [text]

  // Split on number boundaries: look for ". N. " or start-of-string "N. "
  const items = text.split(/(?:^|\.\s+)(?=\d+[.)]\s)/).filter(Boolean)
  if (items.length <= 1) return [text]

  // Re-add the number prefix and trailing period
  return items.map((item) => {
    // Trim and ensure it starts with number
    const trimmed = item.trim()
    if (/^\d+[.)]\s/.test(trimmed)) return trimmed
    return trimmed
  }).filter(Boolean)
}

function RichParagraph({ text }: { text: string }) {
  if (!text) return null

  // First split by actual newlines
  let lines = text.split('\n').map((l) => l.trim()).filter(Boolean)

  // Try to split inline numbered lists within each line
  lines = lines.flatMap((line) => splitInlineNumbers(line))

  // Detect list: all lines start with a list marker
  const isNumbered = lines.length > 1 && lines.every((l) => /^\d+[.)]\s/.test(l))
  const isBullet = lines.length > 1 && lines.every((l) => /^[-*]\s/.test(l))

  if (isNumbered) {
    return (
      <ol className="list-decimal list-outside ml-5 space-y-2.5 text-sm text-text leading-relaxed">
        {lines.map((l, i) => (
          <li key={i}><InlineFormat text={l.replace(/^\d+[.)]\s*/, '')} /></li>
        ))}
      </ol>
    )
  }

  if (isBullet) {
    return (
      <ul className="list-disc list-outside ml-5 space-y-2.5 text-sm text-text leading-relaxed">
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
