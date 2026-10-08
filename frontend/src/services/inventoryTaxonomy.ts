/** Comparison only: never use metadata equivalence to merge products or grades. */
export function taxonomyKey(value: string): string {
  return value.normalize('NFKD').replace(/\p{M}/gu, '').trim().toLowerCase()
    .replace(/\s*>\s*/g, ' > ').replace(/\s+/g, ' ')
    .replace(/\bea7\s+emporio\s+armani\b/g, 'emporio armani')
}

export function uniqueLabels(values: string[]): string[] {
  const labels = new Map<string, string>()
  for (const value of values) {
    const clean = value.trim().replace(/\s+/g, ' ')
    if (clean && !labels.has(taxonomyKey(clean))) labels.set(taxonomyKey(clean), clean)
  }
  return [...labels.values()].sort((a, b) => a.localeCompare(b))
}
