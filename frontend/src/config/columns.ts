import type { Column } from '../components/ui/DataTable'

/**
 * Extended column definition that includes visibility metadata.
 * Used by ColumnPicker to manage which columns are shown.
 */
export interface ColumnDef<T> extends Column<T> {
  /** Whether the column is shown by default (before user customisation) */
  defaultVisible?: boolean
}

/**
 * Helper to create a typed column definition array.
 */
export function defineColumns<T>(cols: ColumnDef<T>[]): ColumnDef<T>[] {
  return cols
}
