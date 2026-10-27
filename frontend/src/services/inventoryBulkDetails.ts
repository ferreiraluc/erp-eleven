import { colorKey } from './inventoryColors'
import type { InventoryItem } from './api'
import { canonicalSize } from './inventoryTaxonomy'

export const detailFields = [
  { key: 'name', label: 'Nome', kind: 'input', max: 200 },
  { key: 'description', label: 'Descrição', kind: 'text', clear: true },
  { key: 'color', label: 'Cor', kind: 'color', max: 50, clear: true },
  { key: 'size', label: 'Tamanho', kind: 'input', max: 50, clear: true },
  { key: 'barcode', label: 'Código de barras', kind: 'input', max: 200, clear: true },
  { key: 'brand', label: 'Marca', kind: 'brand', max: 100, clear: true },
  { key: 'category', label: 'Categoria', kind: 'category', max: 100, clear: true },
  { key: 'unit', label: 'Unidade', kind: 'input', max: 20 },
  { key: 'location', label: 'Localização', kind: 'input', max: 100, clear: true },
  { key: 'supplier_id', label: 'Fornecedor', kind: 'supplier', clear: true },
  { key: 'group_key', label: 'Grade / família', kind: 'input', max: 100, clear: true },
  { key: 'cost_price', label: 'Preço de custo', kind: 'price' },
  { key: 'sale_price', label: 'Preço de venda', kind: 'price' },
  { key: 'cost_currency', label: 'Moeda de custo', kind: 'currency' },
  { key: 'sale_currency', label: 'Moeda da venda', kind: 'currency' },
  { key: 'currency', label: 'Moeda de referência', kind: 'currency' },
  { key: 'min_stock', label: 'Estoque Mínimo', kind: 'number' },
  { key: 'max_stock', label: 'Estoque Máximo', kind: 'number' },
  { key: 'is_active', label: 'Situação do produto', kind: 'status' },
] as const
export type DetailKey = (typeof detailFields)[number]['key']
export type DetailValue = string | number | boolean | null
export type DetailDraft = Record<string, Partial<Record<DetailKey, DetailValue>>>
export function baselineValue(item: InventoryItem, field: DetailKey): DetailValue {
  const value =
    item[field] ??
    (field === 'is_active'
      ? true
      : ['min_stock', 'max_stock', 'cost_price', 'sale_price'].includes(field)
        ? 0
        : '')
  return ['cost_price', 'sale_price'].includes(field) ? Number(value) : value
}
export function detailValue(
  item: InventoryItem,
  field: DetailKey,
  draft: DetailDraft,
): DetailValue {
  return field in (draft[item.id] || {}) ? draft[item.id][field]! : baselineValue(item, field)
}
export function setDetail(
  draft: DetailDraft,
  item: InventoryItem,
  field: DetailKey,
  value: DetailValue,
): DetailDraft {
  const next = { ...draft, [item.id]: { ...draft[item.id] } }
  const baseline = baselineValue(item, field)
  if ((value ?? '') === (baseline ?? '')) delete next[item.id][field]
  else next[item.id][field] = value
  if (!Object.keys(next[item.id]).length) delete next[item.id]
  return next
}
export function scopeOptions(items: InventoryItem[]) {
  const values = new Map<string, string>()
  for (const item of items) {
    if (item.color) values.set(`color:${colorKey(item.color)}`, item.color)
    if (item.size) values.set(`size:${canonicalSize(item.size)}`, canonicalSize(item.size))
  }
  return [...values].map(([value, label]) => ({
    value,
    label,
    kind: value.startsWith('color:') ? 'Cor' : 'Tamanho',
  }))
}
export function inScope(item: InventoryItem, scope: string): boolean {
  return (
    scope === 'all' ||
    scope === `color:${colorKey(item.color || '')}` ||
    scope === `size:${canonicalSize(item.size || '')}`
  )
}
export function detailsError(draft: DetailDraft, items: InventoryItem[] = []): string {
  for (const values of Object.values(draft))
    for (const field of detailFields) {
      if (!(field.key in values)) continue
      const value = values[field.key]
      if (
        field.kind === 'number' &&
        (value === '' ||
          !Number.isInteger(Number(value)) ||
          Number(value) < 0 ||
          Number(value) > 2147483647)
      )
        return 'Confira os limites de estoque: use números inteiros a partir de zero.'
      if (
        field.kind === 'price' &&
        (value === '' ||
          !Number.isFinite(Number(value)) ||
          Number(value) < 0 ||
          Number(value) > 9999999999.99)
      )
        return 'Confira os preços: use valores a partir de zero, dentro do limite permitido.'
      if (['name', 'unit'].includes(field.key) && !String(value ?? '').trim())
        return 'Nome e unidade não podem ficar vazios.'
      if ('max' in field && String(value ?? '').length > field.max)
        return 'Um dos campos ultrapassa o tamanho permitido.'
      if (field.kind === 'currency' && !['USD', 'BRL', 'PYG', 'EUR'].includes(String(value)))
        return 'Selecione uma moeda válida.'
    }
  for (const item of items) {
    if (!('min_stock' in (draft[item.id] || {})) && !('max_stock' in (draft[item.id] || {})))
      continue
    const minimum = Number(detailValue(item, 'min_stock', draft)),
      maximum = Number(detailValue(item, 'max_stock', draft))
    if (maximum && minimum > maximum) return 'Mínimo não pode ser maior que máximo.'
  }
  return ''
}
