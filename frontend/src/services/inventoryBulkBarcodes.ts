import type { InventoryItem } from './api'
import { canonicalSize } from './inventoryTaxonomy'

/** Text only: never turn manufacturer barcodes into numbers or invent a GTIN. */
export function barcodePreview(items: InventoryItem[], values: Record<string, string>, base: string, withSize: boolean, onlyEmpty: boolean) {
  const clean = base.trim()
  if (!clean) throw new Error('Informe o código base.')
  return items.filter(item => !onlyEmpty || !(values[item.id] ?? item.barcode ?? '').trim()).map(item => {
    const size = canonicalSize(item.size || '').replace(/\s+/g, '')
    if (withSize && !size) throw new Error('Há produto sem tamanho. Informe o tamanho ou use apenas o código base.')
    const barcode = clean + (withSize ? size : '')
    if (barcode.length > 200) throw new Error('O código de barras deve ter até 200 caracteres.')
    return { item, before: values[item.id] ?? item.barcode ?? '', after: barcode }
  })
}
export function repeatedBarcodes(items: InventoryItem[], values: Record<string, string>) {
  const codes = new Map<string, number>()
  for (const item of items) {
    const value = (values[item.id] ?? item.barcode ?? '').trim()
    if (value) codes.set(value, (codes.get(value) || 0) + 1)
  }
  return [...codes].filter(([, count]) => count > 1)
}
