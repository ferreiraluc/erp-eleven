/** Comparison only. Original shades, product identities and stock remain intact. */
import { taxonomyKey } from './inventoryTaxonomy'
const groups: Record<string, string[]> = {
  preto: ['preto', 'preta', 'black', 'negro', 'negra'],
  branco: ['branco', 'branca', 'white', 'blanco', 'blanca'],
  azul: ['azul', 'blue'],
  marinho: ['azul marinho', 'azulmarinho', 'navy blue', 'navy', 'azul marino', 'marino', 'marinho'],
  cinza: ['cinza', 'grey', 'gray', 'gris'],
  bege: ['bege', 'beige'],
  marrom: ['marrom', 'brown', 'marron', 'cafe'],
  verde: ['verde', 'green'],
  vermelho: ['vermelho', 'vermelha', 'red', 'rojo', 'roja'],
  amarelo: ['amarelo', 'amarela', 'yellow', 'amarillo', 'amarilla'],
  rosa: ['rosa', 'pink', 'rosado', 'rosada'],
  roxo: ['roxo', 'roxa', 'purple', 'morado', 'morada', 'violeta'],
  laranja: ['laranja', 'orange', 'naranja'],
  dourado: ['dourado', 'dourada', 'gold', 'golden', 'dorado', 'dorada'],
  prata: ['prata', 'silver', 'plateado', 'plateada'],
  offwhite: ['off white', 'off-white', 'offwhite'],
  multicolor: ['multicolor', 'multicolour', 'multicolorido', 'multicolorida'],
}
const aliases = new Map(
  Object.entries(groups).flatMap(([key, values]) => values.map((value) => [value, key] as const)),
)
const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const pattern = new RegExp(
  `(?<![\\p{L}\\p{N}_])(${[...aliases.keys()]
    .sort((a, b) => b.length - a.length)
    .map(escape)
    .join('|')})(?![\\p{L}\\p{N}_])`,
  'gu',
)
export function colorKey(value: string): string {
  const translated = taxonomyKey(value).replace(pattern, (match) => aliases.get(match)!)
  return [
    ...new Set(
      translated
        .split(/\s*(?:[+/,;&]|\b(?:e|y|and)\b)\s*/)
        .map((part) => part.trim())
        .filter(Boolean),
    ),
  ]
    .sort()
    .join(' + ')
}
export function uniqueColors(values: string[]): string[] {
  const labels = new Map<string, string>()
  for (const raw of values) {
    const clean = raw.trim().replace(/\s+/g, ' ')
    if (clean && !labels.has(colorKey(clean))) labels.set(colorKey(clean), clean)
  }
  return [...labels.values()].sort((a, b) => a.localeCompare(b))
}
