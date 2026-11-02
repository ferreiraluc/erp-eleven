import type { AuditEvent, AuditGroup } from './access'

const messages = {
  operations: ['Operações', 'Operaciones', 'Operations'],
  groupedHelp: ['Cada venda reúne seus registros. Outras alterações são agrupadas pela operação confirmada. Os filtros também se aplicam aos detalhes.', 'Cada venta reúne sus registros. Los demás cambios se agrupan por operación confirmada. Los filtros también se aplican a los detalles.', 'Each sale contains its records. Other changes are grouped by confirmed operation. Filters also apply to the details.'],
  records: ['{count} registros', '{count} registros', '{count} records'],
  actors: ['{count} responsáveis', '{count} responsables', '{count} operators'],
  sale: ['Venda #{code}', 'Venta #{code}', 'Sale #{code}'],
  stock: ['Operação de estoque', 'Operación de inventario', 'Stock operation'],
  operation: ['Operação confirmada', 'Operación confirmada', 'Confirmed operation'],
  openSale: ['Abrir venda', 'Abrir venta', 'Open sale'],
  more: ['Carregar mais registros', 'Cargar más registros', 'Load more records'],
  increase: ['Aumentou {quantity} un. em {location}', 'Aumentó {quantity} un. en {location}', 'Added {quantity} units to {location}'],
  decrease: ['Diminuiu {quantity} un. em {location}', 'Disminuyó {quantity} un. en {location}', 'Removed {quantity} units from {location}'],
  transfer: ['Transferiu {quantity} un. de {from} para {to}', 'Transfirió {quantity} un. de {from} a {to}', 'Transferred {quantity} units from {from} to {to}'],
  checked: ['Conferiu o saldo de estoque', 'Revisó el saldo de inventario', 'Checked stock balance'],
  stockUpdated: ['Atualizou os saldos do produto', 'Actualizó el stock del producto', 'Updated product stock'],
  store: ['Loja', 'Tienda', 'Store'], warehouse: ['Depósito', 'Depósito', 'Warehouse'],
  unknownLocation: ['local não informado', 'ubicación sin informar', 'unknown location'],
  stockRecord: ['Movimentação de estoque', 'Movimiento de inventario', 'Stock movement'],
  payment: ['Pagamento da venda', 'Pago de la venta', 'Sale payment'],
  saleItem: ['Item da venda', 'Producto de la venta', 'Sale item'],
  receipt: ['Ticket da venda', 'Ticket de la venta', 'Sale receipt'],
  totalBefore: ['Saldo total anterior', 'Stock total anterior', 'Previous total stock'],
  totalAfter: ['Saldo total após', 'Stock total posterior', 'Resulting total stock'],
  totalStock: ['Estoque total', 'Stock total', 'Total stock'],
  storeBefore: ['Loja antes', 'Tienda antes', 'Store before'], storeAfter: ['Loja depois', 'Tienda después', 'Store after'],
} as const
export type AuditTextKey = keyof typeof messages
export function auditText(key:AuditTextKey, locale:string, params:Record<string,string|number>={}) {
  const index=locale.startsWith('es')?1:locale.startsWith('en')?2:0
  return messages[key][index].replace(/\{(\w+)\}/g,(original,name)=>String(params[name]??original))
}
const object=(value:unknown):Record<string,unknown>=>value&&typeof value==='object'&&!Array.isArray(value)?value as Record<string,unknown>:{}
export function eventContext(event:AuditEvent) { return object(event.changes._context) }
export function productLabel(event:AuditEvent) {
  const p=object(eventContext(event).product)
  return [p.name,p.code].filter(v=>typeof v==='string'&&v).join(' · ')
}
export function stockBalanceText(event:AuditEvent,locale:string) {
  if(event.entity!=='stock_movements'||event.action!=='create') return ''
  const movement=object(eventContext(event).movement)
  const value=(field:string)=>movement[field]??object(event.changes[field]).after
  const before=value('quantity_before'),after=value('quantity_after')
  const storeBefore=value('stock_loja_before'),storeAfter=value('stock_loja_after')
  if(typeof before!=='number'||typeof after!=='number') return ''
  const pair=(label:AuditTextKey,start:number,end:number)=>`${auditText(label,locale)}: ${start.toLocaleString(locale)} → ${end.toLocaleString(locale)}`
  if(typeof storeBefore==='number'&&typeof storeAfter==='number') {
    return [pair('store',storeBefore,storeAfter),pair('warehouse',before-storeBefore,after-storeAfter)].join(' · ')
  }
  return pair('totalStock',before,after)
}
export function eventSummary(event:AuditEvent,locale:string,actionName:(value:string)=>string) {
  const movement={...object(eventContext(event).movement)}
  if(event.entity==='stock_movements') {
    if(event.action!=='create') return `${actionName(event.action)} · ${auditText('stockRecord',locale)}`
    // Older events retained numeric balances but no structural context. Reuse
    // those facts without guessing a location or reconstructing a relationship.
    for(const field of ['quantity_before','quantity_after']) {
      if(typeof movement[field]!=='number') movement[field]=object(event.changes[field]).after
    }
  }
  const place=(value:unknown)=>auditText(value==='loja'?'store':value==='deposito'?'warehouse':'unknownLocation',locale)
  const qty=(value:number)=>Math.abs(value).toLocaleString(locale)
  if (movement.movement_type==='transfer'&&typeof movement.quantity==='number') return auditText('transfer',locale,{quantity:qty(movement.quantity),from:place(movement.location_from),to:place(movement.location_to)})
  if (typeof movement.quantity_before==='number'&&typeof movement.quantity_after==='number') {
    const delta=movement.quantity_after-movement.quantity_before
    const location=delta>0 ? movement.location_to??movement.location_from : movement.location_from??movement.location_to
    return delta ? auditText(delta>0?'increase':'decrease',locale,{quantity:qty(delta),location:place(location)}) : auditText('checked',locale)
  }
  if(event.entity==='stock_movements') return auditText('stockRecord',locale)
  if(event.entity==='inventory_items'&&['stock_loja','stock_deposito','current_stock'].some(k=>k in event.changes)) return auditText('stockUpdated',locale)
  if(event.entity==='pdv_payments') return `${auditText('payment',locale)} · ${actionName(event.action)}`
  if(event.entity==='pdv_sale_items') return `${auditText('saleItem',locale)} · ${actionName(event.action)}`
  if(event.entity==='print_jobs'&&eventContext(event).sale_id) return auditText('receipt',locale)
  return actionName(event.action)
}
export function groupTitle(group:AuditGroup,locale:string,actionName:(value:string)=>string) {
  if(group.kind==='sale') return auditText('sale',locale,{code:group.sale_code||''})
  if(group.kind==='stock') return auditText('stock',locale)
  return group.samples.length===1 ? actionName(group.samples[0].action) : auditText('operation',locale)
}
