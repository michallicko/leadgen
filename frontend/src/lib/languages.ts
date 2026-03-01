/**
 * Canonical language list — single source of truth for all language dropdowns.
 *
 * Sorted alphabetically by label. Used by LanguageSection, RegenerationDialog,
 * and any future component that needs a language picker.
 */

export interface Language {
  code: string
  label: string
  locale: string
}

export const LANGUAGES: Language[] = [
  { code: 'cs', label: 'Czech', locale: 'cs-CZ' },
  { code: 'da', label: 'Danish', locale: 'da-DK' },
  { code: 'nl', label: 'Dutch', locale: 'nl-NL' },
  { code: 'en', label: 'English', locale: 'en-US' },
  { code: 'fi', label: 'Finnish', locale: 'fi-FI' },
  { code: 'fr', label: 'French', locale: 'fr-FR' },
  { code: 'de', label: 'German', locale: 'de-DE' },
  { code: 'it', label: 'Italian', locale: 'it-IT' },
  { code: 'no', label: 'Norwegian', locale: 'nb-NO' },
  { code: 'pl', label: 'Polish', locale: 'pl-PL' },
  { code: 'pt', label: 'Portuguese', locale: 'pt-PT' },
  { code: 'es', label: 'Spanish', locale: 'es-ES' },
  { code: 'sv', label: 'Swedish', locale: 'sv-SE' },
]

/** Map from language code to display label. */
export const LANGUAGE_MAP: Record<string, string> = Object.fromEntries(
  LANGUAGES.map((l) => [l.code, l.label]),
)

/** Map from language code to locale string. */
export const LOCALE_MAP: Record<string, string> = Object.fromEntries(
  LANGUAGES.map((l) => [l.code, l.locale]),
)

/** Formality labels for languages that distinguish formal/informal address. */
export const FORMALITY_LABELS: Record<string, Record<string, string>> = {
  cs: { formal: 'Vy (vykání)', informal: 'Ty (tykání)' },
  de: { formal: 'Sie', informal: 'Du' },
  fr: { formal: 'Vous', informal: 'Tu' },
  es: { formal: 'Usted', informal: 'Tú' },
  it: { formal: 'Lei', informal: 'Tu' },
  pt: { formal: 'O Senhor', informal: 'Você' },
  pl: { formal: 'Pan/Pani', informal: 'Ty' },
  nl: { formal: 'U', informal: 'Je' },
}

/**
 * Format a date string using the locale associated with a language code.
 * Falls back to en-US if the code is unknown.
 */
export function formatDateLocale(iso: string, langCode: string): string {
  const locale = LOCALE_MAP[langCode] ?? 'en-US'
  return new Date(iso).toLocaleDateString(locale, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

/**
 * Format a number using the locale associated with a language code.
 * Falls back to en-US if the code is unknown.
 */
export function formatNumberLocale(
  value: number,
  langCode: string,
  options?: Intl.NumberFormatOptions,
): string {
  const locale = LOCALE_MAP[langCode] ?? 'en-US'
  return new Intl.NumberFormat(locale, options).format(value)
}
