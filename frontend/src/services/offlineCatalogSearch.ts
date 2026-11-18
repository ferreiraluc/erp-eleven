import { searchCatalog, searchable, type CatalogFilters, type CatalogRow, type Searchable } from './catalogSearch'

export type OfflineCatalogItem = Omit<CatalogRow, 'sale_price'> & {
  sale_price: number | null
  unit: string | null
  min_stock: number | null
  max_stock: number | null
  current_stock: number | null
  stock_loja: number | null
  stock_deposito: number | null
  reserved_loja: number | null
  reserved_deposito: number | null
  available_loja: number | null
  available_deposito: number | null
  available_stock: number | null
  /** Consistency when collected, NOT a guarantee of current online stock. */
  stock_confirmed: boolean
  snapshot_at: string
}
export type OfflineCatalogSearchResult = { items: OfflineCatalogItem[]; total: number; syncedAt: number; startedAt: number }
export const MAX_OFFLINE_ROWS = 75000
export const MAX_OFFLINE_BYTES = 64 * 1024 * 1024
export const MAX_THUMBNAIL_BYTES = 128 * 1024 * 1024
export type OfflineCatalogFacets = { brands: string[]; categories: string[]; colors: string[]; sizes: string[] }

// Search only consumes identity/text attributes, never the nullable offline price.
export function offlineIndex(rows: OfflineCatalogItem[]): Searchable[] { return rows.map(row => searchable(row as CatalogRow)) }

/** Only approved fields reach storage. Normalize old nullable attributes and
 * distrust missing/inconsistent balances instead of inventing zero quantities. */
export function normalizeOfflineItem(value: unknown): OfflineCatalogItem {
  if (!value || typeof value !== 'object') throw new Error('invalid')
  const input = value as Record<string, unknown>
  const text = (key: string, max: number, required = false): string => {
    const value = input[key]
    if (value == null && !required) return ''
    if (typeof value !== 'string' || value.length > max || (required && !value)) throw new Error('invalid')
    return value
  }
  const date = (key: string) => { const value = text(key, 64); return value && Number.isFinite(Date.parse(value)) ? value : '' }
  const integer = (key: string): number | null => Number.isInteger(input[key]) && Math.abs(input[key] as number) <= 2_147_483_647 ? input[key] as number : null
  const row: OfflineCatalogItem = {
    id: text('id', 64, true), name: text('name', 200, true), sku_internal: text('sku_internal', 200, true),
    inventory_code: text('inventory_code', 32), barcode: text('barcode', 200),
    brand: text('brand', 100), category: text('category', 100), size: text('size', 50), color: text('color', 50),
    group_key: text('group_key', 100), location: text('location', 100), unit: text('unit', 20), description: text('description', 512),
    sale_price: input.sale_price !== null && input.sale_price !== undefined && Number.isFinite(Number(input.sale_price)) && Number(input.sale_price) >= 0 ? Number(input.sale_price) : null,
    sale_currency: text('sale_currency', 10), is_active: input.is_active === true, has_image: input.has_image === true,
    created_at: date('created_at'), updated_at: date('updated_at'), snapshot_at: date('snapshot_at'),
    min_stock: integer('min_stock'), max_stock: integer('max_stock'),
    current_stock: integer('current_stock'), stock_loja: integer('stock_loja'), stock_deposito: integer('stock_deposito'),
    reserved_loja: integer('reserved_loja'), reserved_deposito: integer('reserved_deposito'),
    available_loja: null, available_deposito: null, available_stock: null, stock_confirmed: false,
  }
  if (!row.snapshot_at) throw new Error('invalid')
  const { current_stock: total, stock_loja: loja, stock_deposito: deposito, reserved_loja: heldL, reserved_deposito: heldD } = row
  if (input.stock_confirmed === true && total !== null && loja !== null && deposito !== null && heldL !== null && heldD !== null && total === loja + deposito && heldL >= 0 && heldD >= 0 && heldL <= Math.max(0, loja) && heldD <= Math.max(0, deposito)) {
    row.stock_confirmed = true; row.available_loja = loja - heldL; row.available_deposito = deposito - heldD; row.available_stock = total - heldL - heldD
  } else row.current_stock = row.stock_loja = row.stock_deposito = row.reserved_loja = row.reserved_deposito = null
  return row
}
export function offlineSearch(index: Searchable[], query: string, filters: CatalogFilters, limit = 50, offset = 0) {
  if (filters.receiving_lot_id) return { items: [], total: 0 }
  const { status, location_stock, ...attributes } = filters
  const supported = !status || ['active', 'inactive', 'out', 'low', 'excess', 'review'].includes(String(status))
  if (!supported || (location_stock && !['loja', 'deposito'].includes(String(location_stock)))) return { items: [], total: 0 }
  const rows = searchCatalog(index, query, { ...attributes, status: status === 'inactive' ? 'inactive' : status === 'active' ? 'active' : undefined }, MAX_OFFLINE_ROWS) as OfflineCatalogItem[]
  const selected = rows.filter(row => {
    if (location_stock && (!row.stock_confirmed || (row[location_stock === 'loja' ? 'available_loja' : 'available_deposito'] ?? 0) <= 0)) return false
    if (status === 'review') return !row.stock_confirmed
    if (['out', 'low', 'excess'].includes(String(status))) {
      if (!row.stock_confirmed || !row.is_active || row.available_stock === null) return false
      if (status === 'out') return row.available_stock <= 0
      if (status === 'low') return row.available_stock > 0 && row.available_stock < (row.min_stock || 0)
      return (row.max_stock || 0) > 0 && row.available_stock > row.max_stock!
    }
    return true
  })
  const start = Math.max(0, Math.trunc(offset) || 0), size = Math.max(1, Math.min(100, Math.trunc(limit) || 50))
  return { items: selected.slice(start, start + size), total: selected.length }
}

export function offlineFacets(rows: OfflineCatalogItem[]): OfflineCatalogFacets {
  const values = (name: 'brand' | 'category' | 'color' | 'size') => [...new Set(rows.map(row => row[name]?.trim()).filter((v): v is string => !!v))].sort((a, b) => a.localeCompare(b)).slice(0, 1000)
  return { brands: values('brand'), categories: values('category'), colors: values('color'), sizes: values('size') }
}

/** A preview from our thumbnail endpoint, never an arbitrary URL or full photo. */
export function validOfflineThumbnail(value: unknown): value is string {
  return typeof value === 'string' && value.length <= 48 * 1024 && /^data:image\/jpeg;base64,\/9j\/[A-Za-z0-9+/]*={0,2}$/.test(value)
}
