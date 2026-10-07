/** Suggestions are drafts only. Identity, variants and quantities belong to the operator. */
export const intakeFields = ['name', 'description', 'category', 'brand', 'size', 'color', 'barcode', 'price'] as const
export type IntakeField = typeof intakeFields[number]
export type IntakeSource = 'photo' | 'label'
export type IntakeDraft = Partial<Record<IntakeField, string>>
export interface IntakeConflict { field: IntakeField; proposed: string; source: IntakeSource }

const normalized = (value: string) => value.trim().replace(/\s+/g, ' ').toLocaleLowerCase()

export function mergeIntake(current: IntakeDraft, incoming: IntakeDraft, source: IntakeSource,
  previous: IntakeDraft = {}) {
  const additions: IntakeDraft = {}
  const conflicts: IntakeConflict[] = []
  for (const field of intakeFields) {
    const value = incoming[field]?.trim()
    // Reopening an already applied reading must not undo manual corrections or deletions.
    if (!value || value === previous[field]) continue
    const existing = current[field]?.trim()
    if (!existing) additions[field] = value
    else if (normalized(existing) !== normalized(value)) conflicts.push({ field, proposed: value, source })
  }
  return { additions, conflicts }
}
