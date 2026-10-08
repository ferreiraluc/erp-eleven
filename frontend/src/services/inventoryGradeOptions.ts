export type GradePreset = { label: string; sizes: string[]; custom?: true }

export const GRADE_PRESETS: GradePreset[] = [
  { label: 'P → 2XL', sizes: ['P', 'M', 'L', 'XL', '2XL'] },
  { label: '46 → 54', sizes: ['46', '48', '50', '52', '54'] },
  { label: 'Calçados 38–42', sizes: ['38', '39', '40', '41', '42'] },
  { label: 'Calçados 38–44', sizes: ['38', '39', '40', '41', '42', '43', '44'] },
  { label: 'Calças 30–40', sizes: ['30', '31', '32', '33', '34', '36', '38', '40'] },
]
export const QUICK_COLORS = ['Navy', 'Branco', 'Preto', 'Red', 'Green']
export const PRESETS_KEY = 'inv_grade_custom_presets'
export const COLORS_KEY = 'inv_grade_custom_colors'
export const STORAGE_ERROR = 'Não foi possível salvar neste navegador. Verifique o armazenamento e tente novamente.'

export function optionKey(value: string) {
  return value.trim().replace(/\s+/g, ' ').toLocaleLowerCase()
}

export function parseGradeSizes(value: string): string[] {
  return [...new Set(value.toUpperCase().split(/[\s,;]+/).filter(Boolean))]
}

export function readPreference(key: string): string | null {
  try { return localStorage.getItem(key) } catch { return null }
}

export function savePreference(key: string, value: string): boolean {
  try { localStorage.setItem(key, value); return true } catch { return false }
}

function readOptions(key: string): unknown[] {
  try {
    const value: unknown = JSON.parse(readPreference(key) || '[]')
    return Array.isArray(value) ? value : []
  } catch { return [] }
}

export function readCustomPresets(): GradePreset[] {
  const result: GradePreset[] = []
  const names = new Set(GRADE_PRESETS.map(p => optionKey(p.label)))
  for (const value of readOptions(PRESETS_KEY)) {
    if (!value || typeof value !== 'object') continue
    const p = value as Record<string, unknown>
    if (typeof p.label !== 'string' || !Array.isArray(p.sizes)) continue
    const label = p.label.trim().replace(/\s+/g, ' ')
    const sizes = parseGradeSizes(p.sizes.filter(s => typeof s === 'string').join(','))
    if (!label || !sizes.length || names.has(optionKey(label))) continue
    result.push({ label, sizes, custom: true })
    names.add(optionKey(label))
  }
  return result
}

export function readCustomColors(): string[] {
  const result: string[] = []
  const names = new Set(QUICK_COLORS.map(optionKey))
  for (const value of readOptions(COLORS_KEY)) {
    if (typeof value !== 'string') continue
    const color = value.trim().replace(/\s+/g, ' ')
    if (!color || names.has(optionKey(color))) continue
    result.push(color)
    names.add(optionKey(color))
  }
  return result
}
