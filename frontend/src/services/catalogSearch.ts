/** Provisional device search; the server still owns filters, identity and balances. */
import type { InventoryItem } from './api'
import { taxonomyKey, canonicalSize } from './inventoryTaxonomy'
import { colorKey } from './inventoryColors'
export type CatalogRow = Pick<
  InventoryItem,
  | 'id'
  | 'name'
  | 'inventory_code'
  | 'sku_internal'
  | 'barcode'
  | 'brand'
  | 'category'
  | 'size'
  | 'color'
  | 'group_key'
  | 'location'
  | 'sale_price'
  | 'sale_currency'
  | 'is_active'
  | 'has_image'
  | 'created_at'
  | 'updated_at'
  | 'description'
>
export type CatalogFilters = Record<string, string | boolean | undefined>
const compact = (value: string) => value.replace(/[-_./\s]/g, '')
const key = (value: string) =>
  taxonomyKey(value)
    .replace(/\b(?:t-?shirts?|t shirts?|tsirt|tshrit|camsetas?|camisetas?)\b/g, 'camiseta')
    .replace(/\bcalsas?\b/g, 'calca')
export function oneLetterTypo(a: string, b: string) {
  if (a.length !== b.length) return false
  let count = 0
  for (let i = 0; i < a.length; i++)
    if (a[i] !== b[i]) {
      // A mistyped model letter is a suggestion. Numbers are never substituted.
      if (/\d/.test(a[i] + b[i])) return false
      if (++count > 1) return false
    }
  return count === 1
}
export function nearWord(a: string, b: string) {
  if (Math.abs(a.length - b.length) > 1 || a.length < 4) return false
  if (a.length === b.length)
    return (
      oneLetterTypo(a, b) ||
      [...a].some((_, i) => a.slice(0, i) + a[i + 1] + a[i] + a.slice(i + 2) === b)
    )
  const [short, long] = a.length < b.length ? [a, b] : [b, a]
  return [...long].some((_, i) => long.slice(0, i) + long.slice(i + 1) === short)
}
export function searchable(row: CatalogRow) {
  const text = key(
    [
      row.name,
      row.description,
      row.inventory_code,
      row.sku_internal,
      row.barcode,
      row.brand,
      row.category,
      row.color,
      row.group_key,
    ]
      .filter(Boolean)
      .join(' '),
  )
  return { row, text, words: text.split(/[^a-z0-9]+/).filter(Boolean), compact: compact(text) }
}
export type Searchable = ReturnType<typeof searchable>
export function searchCatalog(
  index: Searchable[],
  query: string,
  filters: CatalogFilters = {},
  limit = 50,
) {
  // Do not guess filters which require fresh quantities or receiving-lot membership.
  if (
    filters.receiving_lot_id ||
    filters.location_stock ||
    (filters.status && !['active', 'inactive'].includes(String(filters.status)))
  )
    return []
  const q = key(query.trim()),
    terms = q
      .replace(/\b([a-z]{1,3})[\s-]+(\d{2,})\b/g, '$1$2')
      .split(/\s+/)
      .filter(Boolean)
  const exactQr = /^INV-[A-Z0-9]{6}$/i.test(query.trim())
  const matches: { entry: Searchable; rank: number }[] = []
  for (const entry of index) {
    const r = entry.row
    if (
      (filters.status === 'active' && !r.is_active) ||
      (filters.status === 'inactive' && r.is_active)
    )
      continue
    if (filters.ungrouped_only && r.group_key) continue
    if (
      filters.category === '__uncategorized__'
        ? !!r.category?.trim()
        : filters.category && key(r.category || '') !== key(String(filters.category))
    )
      continue
    if (filters.brand && key(r.brand || '') !== key(String(filters.brand))) continue
    if (filters.color && colorKey(r.color || '') !== colorKey(String(filters.color))) continue
    if (filters.size && canonicalSize(r.size || '') !== canonicalSize(String(filters.size)))
      continue
    if (filters.location && key(r.location || '') !== key(String(filters.location))) continue
    let rank = 0
    if (exactQr) {
      if (r.inventory_code?.toUpperCase() !== query.trim().toUpperCase()) continue
      rank = -10
    } else {
      let found = true
      for (const term of terms) {
        if (/^(p|s|m|g|l|gg|xl|xxl|2xl)$/i.test(term)) {
          if (canonicalSize(r.size || '') !== canonicalSize(term)) {
            found = false
            break
          }
        } else if (entry.text.includes(term) || entry.compact.includes(compact(term))) continue
        else if (/\d/.test(term)) {
          if (
            term.length < 5 ||
            !/[a-z]/.test(term) ||
            !entry.words.some((word) => oneLetterTypo(term, word))
          ) {
            found = false
            break
          }
          rank += 3
        } else if (entry.words.some((word) => nearWord(term, word))) rank += 2
        else {
          found = false
          break
        }
      }
      if (!found) continue
      if (
        [r.inventory_code, r.sku_internal, r.barcode].some(
          (value) => value?.toLowerCase() === query.trim().toLowerCase(),
        )
      )
        rank = -10
    }
    matches.push({ entry, rank })
  }
  matches.sort(
    (a, b) =>
      a.rank - b.rank ||
      (query
        ? a.entry.row.name.localeCompare(b.entry.row.name)
        : b.entry.row.created_at.localeCompare(a.entry.row.created_at)) ||
      a.entry.row.id.localeCompare(b.entry.row.id),
  )
  return matches.slice(0, limit).map(({ entry }) => entry.row)
}
export function cachedItem(row: CatalogRow): InventoryItem {
  return {
    ...row,
    unit: 'un',
    currency: row.sale_currency,
    cost_currency: '',
    cost_price: 0,
    min_stock: 0,
    max_stock: 0,
    current_stock: null,
    stock_loja: null,
    stock_deposito: null,
    image_data: null,
    alert_level: 'unknown',
    catalog_cached: true,
  }
}
