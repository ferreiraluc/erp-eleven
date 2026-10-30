import api from './api'
import {
  labelRequest,
  type LabelBatch,
  type LabelLine,
  type LabelProduct,
  type LabelRequest,
} from './productLabels'
import type { ProductLabelLayout } from './productLabelDesign'

export interface ReplenishmentProduct extends LabelProduct {
  sale_price: string
  sale_currency: string
  brand: string | null
  location: string | null
  has_image: boolean | null
  updated_at: string
  blocked_reason: string | null
}
export interface ReplenishmentLine extends LabelLine {
  sale_price: string
  sale_currency: string
  expected_stock_loja: number
  expected_stock_deposito: number
  expected_current_stock: number
}
export interface ReplenishmentRequest extends LabelRequest {
  items: ReplenishmentLine[]
}
export interface ReplenishmentResult extends LabelBatch {
  replenished_items: number
  movements: {
    id: string
    item_id: string
    quantity: number
    stock_loja: number
    stock_deposito: number
    current_stock: number
  }[]
  created_at: string
}
export interface ReplenishmentPage {
  items: ReplenishmentProduct[]
  total: number
  page: number
  page_size: number
}

export const inventoryReplenishment = {
  list: (q: string, page: number, signal?: AbortSignal) =>
    api
      .get<ReplenishmentPage>('/api/inventory-replenishment/items', { params: { q, page }, signal })
      .then((r) => r.data),
  confirm: (body: ReplenishmentRequest) =>
    api.post<ReplenishmentResult>('/api/inventory-replenishment/confirm', body).then((r) => r.data),
}

export function canReplenish(item: ReplenishmentProduct) {
  return (
    !item.blocked_reason &&
    item.stock_loja === 0 &&
    Number.isInteger(item.stock_deposito) &&
    item.stock_deposito! > 0 &&
    item.current_stock === item.stock_deposito &&
    /^INV-[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{6}$/.test(item.inventory_code || '')
  )
}

/** One frozen confirmation authorizes both the transfer and its labels. */
export function replenishmentRequest(
  rows: (ReplenishmentProduct & { copies: number })[],
  key: string,
  layout?: ProductLabelLayout,
): ReplenishmentRequest {
  if (
    !rows.length ||
    rows.length > 100 ||
    new Set(rows.map((row) => row.id)).size !== rows.length ||
    rows.some((row) => !canReplenish(row) || row.copies > row.stock_deposito!)
  )
    throw new Error('invalid-replenishment')
  const body = labelRequest(rows, key, layout)
  return {
    ...body,
    items: body.items.map((line, index) => ({
      ...line,
      sale_price: rows[index].sale_price,
      sale_currency: rows[index].sale_currency,
      expected_stock_loja: rows[index].stock_loja!,
      expected_stock_deposito: rows[index].stock_deposito!,
      expected_current_stock: rows[index].current_stock!,
    })),
  }
}

/** Invalid saved data must not silently become a new request after a lost response. */
export function restoreReplenishmentRequest(value: string): ReplenishmentRequest {
  const body = JSON.parse(value) as ReplenishmentRequest
  if (
    !body ||
    body.confirm !== true ||
    typeof body.request_key !== 'string' ||
    !/^[a-zA-Z0-9-]{1,128}$/.test(body.request_key) ||
    !Array.isArray(body.items) ||
    (body.layout_id !== undefined &&
      (typeof body.layout_id !== 'string' || !Number.isInteger(body.layout_revision)))
  ) {
    throw new Error('invalid-replenishment')
  }
  const rows = body.items.map((line) => {
    if (
      !line ||
      typeof line.item_id !== 'string' ||
      typeof line.name !== 'string' ||
      typeof line.code !== 'string' ||
      typeof line.sale_price !== 'string' ||
      !line.sale_price.trim() ||
      !Number.isFinite(Number(line.sale_price)) ||
      Number(line.sale_price) < 0 ||
      typeof line.sale_currency !== 'string' ||
      !line.sale_currency.trim() ||
      line.sale_currency.length > 10 ||
      ![line.color, line.size].every((value) => value === null || typeof value === 'string')
    ) {
      throw new Error('invalid-replenishment')
    }
    return {
      id: line.item_id,
      name: line.name,
      inventory_code: line.code,
      color: line.color,
      size: line.size,
      group_key: null,
      stock_loja: line.expected_stock_loja,
      stock_deposito: line.expected_stock_deposito,
      current_stock: line.expected_current_stock,
      sale_price: line.sale_price,
      sale_currency: line.sale_currency,
      brand: null,
      location: null,
      has_image: false,
      updated_at: '',
      blocked_reason: null,
      copies: line.copies,
    }
  })
  replenishmentRequest(rows, body.request_key)
  return body
}
