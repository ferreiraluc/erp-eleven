/** Comparison only: never use metadata equivalence to merge products or grades. */
export function taxonomyKey(value: string): string {
  return value.normalize('NFKD').replace(/\p{M}/gu, '').trim().toLowerCase()
    .replace(/\s*>\s*/g, ' > ').replace(/\s+/g, ' ')
    .replace(/\b(?:dolce\s*&?\s*gabbana|d\s*&\s*g|dg)\b/g, 'dolce & gabbana')
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

/** Only explicit clothing aliases. Numeric footwear sizes retain their own scale. */
export function canonicalSize(value: string): string {
  const clean = value.trim().replace(/\s+/g, ' ')
  return ({ P: 'S', S: 'S', M: 'M', G: 'L', L: 'L', GG: 'XL', XL: 'XL', XXL: '2XL', '2XL': '2XL' } as Record<string, string>)[clean.toUpperCase()] || clean
}

export function canonicalBrand(value: string): string {
  return /^(dg|d&g|dolce&?gabbana)$/.test(value.toLowerCase().replace(/\s+/g, '')) ? 'Dolce & Gabbana' : value
}
