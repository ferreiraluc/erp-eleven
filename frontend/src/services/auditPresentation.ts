import type { AuditEvent, AuditGroup } from './access'

const messages = {
  gradeLinked: ['Vinculou {count} produtos à grade {name}', 'Vinculó {count} productos al grupo {name}', 'Linked {count} products to group {name}'],
  operations: ['Operações', 'Operaciones', 'Operations'],
  groupedHelp: ['Cada venda reúne seus registros. Outras alterações são agrupadas pela operação confirmada. Os filtros também se aplicam aos detalhes.', 'Cada venta reúne sus registros. Los demás cambios se agrupan por operación confirmada. Los filtros también se aplican a los detalles.', 'Each sale contains its records. Other changes are grouped by confirmed operation. Filters also apply to the details.'],
  record: ['1 registro', '1 registro', '1 record'],
  records: ['{count} registros', '{count} registros', '{count} records'],
  actors: ['{count} responsáveis', '{count} responsables', '{count} operators'],
  sale: ['Venda #{code}', 'Venta #{code}', 'Sale #{code}'],
  saleLabel: ['Venda', 'Venta', 'Sale'],
  saleRecorded: ['Venda registrada', 'Venta registrada', 'Sale recorded'],
  saleChanged: ['Venda alterada', 'Venta modificada', 'Sale updated'],
  saleDeleted: ['Venda excluída', 'Venta eliminada', 'Sale deleted'],
  operationalSale: ['Venda operacional', 'Venta operativa', 'Operational sale'],
  saleTotal: ['Total da venda', 'Total de la venta', 'Sale total'],
  seller: ['Vendedor', 'Vendedor', 'Salesperson'],
  ticket: ['Ticket', 'Ticket', 'Receipt'],
  examples: ['Registros desta operação', 'Registros de esta operación', 'Records in this operation'],
  technical: ['Referências técnicas', 'Referencias técnicas', 'Technical references'],
  entity: ['Tipo de registro', 'Tipo de registro', 'Record type'],
  identifier: ['Identificador', 'Identificador', 'Identifier'],
  channel: ['Canal', 'Canal', 'Channel'],
  changedFields: ['Campos alterados', 'Campos modificados', 'Changed fields'],
  createEntity: ['Cadastro de {entity}', 'Registro de {entity}', '{entity} created'],
  updateEntity: ['Alteração de {entity}', 'Cambio de {entity}', '{entity} updated'],
  deleteEntity: ['Exclusão de {entity}', 'Eliminación de {entity}', '{entity} deleted'],
  updateFields: ['Alteração de {fields} {owner}', 'Cambio de {fields} {owner}', '{fields} changed {owner}'],
  otherFields: ['e outros campos', 'y otros campos', 'and other fields'],
  batchChange: ['Alteração em lote de {entity}', 'Cambio en lote de {entity}', 'Bulk update of {entity}'],
  batchDelete: ['Exclusão em lote de {entity}', 'Eliminación en lote de {entity}', 'Bulk deletion of {entity}'],
  login: ['Login', 'Inicio de sesión', 'Login'],
  logout: ['Logout', 'Cierre de sesión', 'Logout'],
  login_failed: ['Tentativa de login recusada', 'Intento de acceso rechazado', 'Login attempt denied'],
  order_reserve: ['Pedido reservado', 'Pedido reservado', 'Order reserved'],
  order_edit: ['Pedido alterado', 'Pedido modificado', 'Order updated'],
  order_payment: ['Pagamento do pedido', 'Pago del pedido', 'Order payment'],
  order_conditional_dispatch: ['Saída de peças em condicional', 'Salida de prendas en consignación', 'Items dispatched on approval'],
  order_conditional_return: ['Devolução de peças em condicional', 'Devolución de prendas en consignación', 'Approval items returned'],
  order_refund: ['Devolução de pagamento do pedido', 'Reembolso del pedido', 'Order payment refunded'],
  order_cancel: ['Pedido cancelado', 'Pedido cancelado', 'Order cancelled'],
  order_checkout: ['Pedido convertido em venda', 'Pedido convertido en venta', 'Order converted to sale'],
  orders_archived: ['Pedidos arquivados', 'Pedidos archivados', 'Orders archived'],
  productRegistration: ['Cadastro de produto', 'Registro de producto', 'Product registration'],
  batchCreate: ['Cadastros de {entity}', 'Registros de {entity}', '{entity} registrations'],
  batchUpdates: ['Alterações de {entity}', 'Cambios de {entity}', '{entity} updates'],
  batchDeletes: ['Exclusões de {entity}', 'Eliminaciones de {entity}', '{entity} deletions'],
  stock: ['Operação de estoque', 'Operación de inventario', 'Stock operation'],
  operation: ['Operação confirmada', 'Operación confirmada', 'Confirmed operation'],
  openSale: ['Abrir venda', 'Abrir venta', 'Open sale'],
  more: ['Carregar mais registros', 'Cargar más registros', 'Load more records'],
  increase: ['Entrada de estoque · {quantity} un. · {location}', 'Entrada de inventario · {quantity} un. · {location}', 'Stock entry · {quantity} units · {location}'],
  decrease: ['Saída de estoque · {quantity} un. · {location}', 'Salida de inventario · {quantity} un. · {location}', 'Stock removal · {quantity} units · {location}'],
  transfer: ['Transferência de estoque · {quantity} un. · {from} → {to}', 'Transferencia de inventario · {quantity} un. · {from} → {to}', 'Stock transfer · {quantity} units · {from} → {to}'],
  entry: ['Entrada de estoque', 'Entrada de inventario', 'Stock entry'],
  exit: ['Saída de estoque', 'Salida de inventario', 'Stock removal'],
  adjustment: ['Ajuste de estoque', 'Ajuste de inventario', 'Stock adjustment'],
  stockTransfer: ['Transferência de estoque', 'Transferencia de inventario', 'Stock transfer'],
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
type Localized = readonly [string, string, string]
const localized = (text:Localized, locale:string) => text[locale.startsWith('es')?1:locale.startsWith('en')?2:0]
const object = (value:unknown):Record<string,unknown> => value&&typeof value==='object'&&!Array.isArray(value)?value as Record<string,unknown>:{}
const number = (value:unknown):number|null => {
  if(typeof value==='number') return Number.isFinite(value)?value:null
  if(typeof value==='string'&&value.trim()&&/^-?\d+(?:\.\d+)?$/.test(value.trim())) return Number.isFinite(Number(value))?Number(value):null
  return null
}
const changedValue = (event:AuditEvent,key:string) => {
  const value=object(event.changes[key])
  return event.action==='delete'?value.before:value.after
}
const entities:Record<string,Localized> = {
  clientes:['cliente','cliente','Customer'], pdv_clientes:['cliente do PDV','cliente del PDV','POS customer'],
  inventory_items:['produto','producto','Product'], stock_movements:['movimentação de estoque','movimiento de inventario','Stock movement'],
  pdv_sales:['venda','venta','Sale'], vendas:['venda operacional','venta operativa','Operational sale'],
  pdv_payments:['pagamento da venda','pago de la venta','Sale payment'], pdv_sale_items:['item da venda','producto de la venta','Sale item'],
  pedidos:['pedido','pedido','Order'], rastreamentos:['rastreio','seguimiento','Tracking'],
  saved_addresses:['endereço','dirección','Address'], print_jobs:['solicitação de impressão','solicitud de impresión','Print request'],
  print_devices:['impressora','impresora','Printer'], print_senders:['remetente','remitente','Sender'],
  usuarios:['usuário','usuario','User'], suppliers:['fornecedor','proveedor','Supplier'],
  inventory_sessions:['conferência de estoque','revisión de inventario','Stock count'],
  inventory_session_items:['item da conferência','producto de la revisión','Stock count item'],
  inventory_receiving_lots:['lote de recebimento','lote recibido','Receiving batch'],
  exchange_rates:['cotação','cotización','Exchange rate'], vendedores:['vendedor','vendedor','Salesperson'],
}
const entityPlurals:Record<string,Localized> = {
  clientes:['clientes','clientes','Customers'], pdv_clientes:['clientes do PDV','clientes del PDV','POS customers'],
  inventory_items:['produtos','productos','Products'], stock_movements:['movimentações de estoque','movimientos de inventario','Stock movements'],
  pedidos:['pedidos','pedidos','Orders'], rastreamentos:['rastreios','seguimientos','Tracking records'],
  saved_addresses:['endereços','direcciones','Addresses'], pdv_payments:['pagamentos','pagos','Payments'],
}
const fieldLabels:Record<string,Localized> = {
  nome:['Nome','Nombre','Name'], name:['Nome','Nombre','Name'], description:['Descrição','Descripción','Description'],
  telefone:['Telefone','Teléfono','Phone'], email:['E-mail','Correo','Email'], endereco:['Endereço','Dirección','Address'],
  cpf:['CPF','CPF','CPF'], documentos:['Documentos','Documentos','Documents'], ativo:['Situação','Estado','Status'],
  active:['Situação','Estado','Status'], is_active:['Situação','Estado','Status'], status:['Situação','Estado','Status'], state:['Estado','Estado','State'],
  brand:['Marca','Marca','Brand'], category:['Categoria','Categoría','Category'], size:['Tamanho','Talla','Size'], color:['Cor','Color','Color'],
  unit:['Unidade','Unidad','Unit'], location:['Localização','Ubicación','Location'], group_key:['Grade','Grupo','Variant group'],
  barcode:['Código de barras','Código de barras','Barcode'], inventory_code:['Código interno','Código interno','Internal code'], sku_internal:['SKU','SKU','SKU'],
  supplier_id:['Fornecedor','Proveedor','Supplier'], cost_price:['Preço de custo','Precio de costo','Cost price'],
  sale_price:['Preço de venda','Precio de venta','Sale price'], currency:['Moeda','Moneda','Currency'], moeda:['Moeda','Moneda','Currency'],
  cost_currency:['Moeda de custo','Moneda de costo','Cost currency'], sale_currency:['Moeda de venda','Moneda de venta','Sale currency'],
  min_stock:['Estoque mínimo','Stock mínimo','Minimum stock'], max_stock:['Estoque máximo','Stock máximo','Maximum stock'],
  current_stock:['Estoque total','Stock total','Total stock'], stock_loja:['Estoque na loja','Stock en tienda','Store stock'], stock_deposito:['Estoque no depósito','Stock en depósito','Warehouse stock'],
  reserved_loja:['Reservado na loja','Reservado en tienda','Reserved in store'], reserved_deposito:['Reservado no depósito','Reservado en depósito','Reserved in warehouse'],
  quantity:['Quantidade','Cantidad','Quantity'], quantity_before:['Saldo total anterior','Stock total anterior','Previous total stock'], quantity_after:['Saldo total após','Stock total posterior','Resulting total stock'],
  stock_loja_before:['Loja antes','Tienda antes','Store before'], stock_loja_after:['Loja depois','Tienda después','Store after'],
  total_gs:['Total em G$','Total en G$','Total in G$'], valor_bruto:['Valor bruto','Importe bruto','Gross amount'], valor_liquido:['Valor líquido','Importe neto','Net amount'],
  usd_rate_gs:['Câmbio do dólar','Tipo de cambio del dólar','USD exchange rate'], desconto_gs:['Desconto em G$','Descuento en G$','Discount in G$'],
  subtotal_gs:['Subtotal em G$','Subtotal en G$','Subtotal in G$'], vendedor_id:['Vendedor','Vendedor','Salesperson'], cliente_id:['Cliente','Cliente','Customer'],
  cliente_nome:['Nome do cliente','Nombre del cliente','Customer name'], role:['Perfil','Perfil','Role'], sales_scope:['Acesso às vendas','Acceso a ventas','Sales access'],
  affected_rows:['Registros afetados','Registros afectados','Affected records'], merged_into_id:['Unificação de cliente','Unificación de cliente','Customer merge'],
  label_status:['Situação da etiqueta','Estado de la etiqueta','Label status'], method:['Forma de pagamento','Forma de pago','Payment method'],
  amount_gs:['Pagamento em G$','Pago en G$','Payment in G$'], amount_original:['Valor pago','Importe pagado','Paid amount'],
  refund_gs:['Valor devolvido em G$','Importe devuelto en G$','Refund in G$'], returned_quantity:['Quantidade devolvida','Cantidad devuelta','Returned quantity'],
  movement_type:['Tipo de movimentação','Tipo de movimiento','Movement type'], location_from:['Origem','Origen','Origin'], location_to:['Destino','Destino','Destination'],
  created_at:['Data do cadastro','Fecha de registro','Created at'], updated_at:['Data da alteração','Fecha del cambio','Updated at'],
}
const technicalFields=new Set(['id','created_at','updated_at','created_by','deleted_by','version','request_id','event_id','preview_hash','destination_ids'])
export function auditFieldName(key:string,locale:string) { return fieldLabels[key]?localized(fieldLabels[key],locale):key.replaceAll('_',' ') }
export function auditEntityName(entity:string|null,locale:string) { return entity&&entities[entity]?localized(entities[entity],locale):entity||'—' }
export function eventContext(event:AuditEvent) { return object(event.changes._context) }
export function productLabel(event:AuditEvent) {
  const p=object(eventContext(event).product)
  return [p.name,p.code].filter(v=>typeof v==='string'&&v).join(' · ')
}
export function stockBalanceText(event:AuditEvent,locale:string) {
  if(event.entity!=='stock_movements'||event.action!=='create') return ''
  const movement=object(eventContext(event).movement)
  const value=(field:string)=>number(movement[field]??object(event.changes[field]).after)
  const before=value('quantity_before'),after=value('quantity_after')
  const storeBefore=value('stock_loja_before'),storeAfter=value('stock_loja_after')
  if(before===null||after===null) return ''
  const pair=(label:AuditTextKey,start:number,end:number)=>`${auditText(label,locale)}: ${start.toLocaleString(locale)} → ${end.toLocaleString(locale)}`
  if(storeBefore!==null&&storeAfter!==null) return [pair('store',storeBefore,storeAfter),pair('warehouse',before-storeBefore,after-storeAfter)].join(' · ')
  return pair('totalStock',before,after)
}
export function saleFacts(event:AuditEvent,locale:string) {
  const sale=object(eventContext(event).sale)
  // Never reinterpret item/payment totals as the sale total, nor use today's FX.
  const total=number(sale.total_gs??(event.entity==='pdv_sales'?changedValue(event,'total_gs'):undefined))
  const rate=number(sale.usd_rate_gs)
  const amount=total===null?'':rate!==null&&rate>0?`U$ ${(total/rate).toLocaleString(locale,{minimumFractionDigits:2,maximumFractionDigits:2})}`:`G$ ${total.toLocaleString(locale,{maximumFractionDigits:2})}`
  return {seller:typeof sale.seller_name==='string'?sale.seller_name:'',amount}
}
function entitySummary(event:AuditEvent,locale:string,actionName:(value:string)=>string) {
  const entity=event.entity&&entities[event.entity]?auditEntityName(event.entity,locale):''
  const action=event.action
  if(!entity) return actionName(action)
  if(action==='create'||action==='delete'||action==='bulk_update'||action==='bulk_delete') return auditText(action==='create'?'createEntity':action==='delete'?'deleteEntity':action==='bulk_update'?'batchChange':'batchDelete',locale,{entity})
  if(action==='update') {
    const keys=Object.keys(event.changes).filter(key=>!key.startsWith('_')&&!technicalFields.has(key))
    const customer=event.entity==='clientes'||event.entity==='pdv_clientes'
    const product=event.entity==='inventory_items'
    if(keys.length&&keys.every(key=>key in fieldLabels)&&(customer||product)) {
      const fields=keys.slice(0,3).map(key=>auditFieldName(key,locale).toLocaleLowerCase(locale)).join(', ')+(keys.length>3?` ${auditText('otherFields',locale)}`:'')
      const owner=localized(customer?['do cliente','del cliente','for customer']:['do produto','del producto','for product'],locale)
      return auditText('updateFields',locale,{fields,owner})
    }
    return auditText('updateEntity',locale,{entity})
  }
  return `${actionName(action)} · ${entity}`
}
export function movementKind(event:AuditEvent):'entry'|'exit'|'stockTransfer'|null {
  if(event.entity!=='stock_movements'||event.action!=='create') return null
  const movement=object(eventContext(event).movement)
  if(movement.movement_type==='transfer') return 'stockTransfer'
  const before=number(movement.quantity_before??object(event.changes.quantity_before).after)
  const after=number(movement.quantity_after??object(event.changes.quantity_after).after)
  if(before===null||after===null||before===after) return null
  return after>before?'entry':'exit'
}
const customActions=new Set(['login','logout','login_failed','order_reserve','order_edit','order_payment','order_conditional_dispatch','order_conditional_return','order_refund','order_cancel','order_checkout','orders_archived'])
export function eventSummary(event:AuditEvent,locale:string,actionName:(value:string)=>string) {
  if(customActions.has(event.action)) return auditText(event.action as AuditTextKey,locale)
  if(event.entity==='inventory_grade_links'&&event.action==='grade_link') return auditText('gradeLinked',locale,{count:Array.isArray(event.changes.item_ids)?event.changes.item_ids.length:0,name:typeof event.changes.target_group_key==='string'?event.changes.target_group_key:''})
  if(event.entity==='stock_movements') {
    if(event.action!=='create') return entitySummary(event,locale,actionName)
    const movement=object(eventContext(event).movement)
    const place=(value:unknown)=>auditText(value==='loja'?'store':value==='deposito'?'warehouse':'unknownLocation',locale)
    const qty=(value:number)=>Math.abs(value).toLocaleString(locale)
    const quantity=number(movement.quantity)
    if(movement.movement_type==='transfer'&&quantity!==null) return auditText('transfer',locale,{quantity:qty(quantity),from:place(movement.location_from),to:place(movement.location_to)})
    const before=number(movement.quantity_before??object(event.changes.quantity_before).after),after=number(movement.quantity_after??object(event.changes.quantity_after).after)
    if(before!==null&&after!==null) {
      const delta=after-before
      const location=delta>0?movement.location_to??movement.location_from:movement.location_from??movement.location_to
      return delta?auditText(delta>0?'increase':'decrease',locale,{quantity:qty(delta),location:place(location)}):auditText('checked',locale)
    }
    return auditText('stockRecord',locale)
  }
  if(event.entity==='pdv_sales') {
    const facts=saleFacts(event,locale)
    const label=event.action==='create'?'saleRecorded':event.action==='update'?'saleChanged':event.action==='delete'?'saleDeleted':null
    // A return/cancellation is an action, not another sale or a refund of its full total.
    return label?[auditText(label,locale),facts.seller,facts.amount].filter(Boolean).join(' · '):actionName(event.action)
  }
  if(event.entity==='vendas') {
    const sale=object(eventContext(event).operational_sale)
    const amount=number(sale.amount??changedValue(event,'valor_bruto')),currency=sale.currency??changedValue(event,'moeda')
    const seller=typeof sale.seller_name==='string'?sale.seller_name:''
    const total=amount!==null&&typeof currency==='string'?`${currency} ${amount.toLocaleString(locale,{minimumFractionDigits:2,maximumFractionDigits:2})}`:''
    return [entitySummary(event,locale,actionName),seller,total].filter(Boolean).join(' · ')
  }
  if(event.entity==='print_jobs'&&eventContext(event).sale_id) return `${auditText('receipt',locale)} · ${actionName(event.action)}`
  return entitySummary(event,locale,actionName)
}
export function groupTitle(group:AuditGroup,locale:string,actionName:(value:string)=>string) {
  const representative=group.summary_event??(group.event_count===1?group.samples[0]:null)
  if(group.kind==='sale') {
    const event=representative??group.samples.find(e=>e.entity==='pdv_sales')??group.samples.find(e=>Object.keys(object(eventContext(e).sale)).length>0)
    const facts=event?saleFacts(event,locale):{seller:'',amount:''}
    const isSaleEvent=event?.entity==='pdv_sales'
    const action=event?.action
    const isExplicitAction=isSaleEvent&&action!=='create'&&action!=='update'
    const label=isExplicitAction?(action==='delete'?auditText('saleDeleted',locale):actionName(action||'')):auditText('saleLabel',locale)
    const total=facts.amount&&isExplicitAction?`${auditText('saleTotal',locale)}: ${facts.amount}`:facts.amount
    return facts.seller||total?[label,facts.seller,total].filter(Boolean).join(' · '):isExplicitAction?label:group.sale_code?auditText('sale',locale,{code:group.sale_code}):label
  }
  if(group.event_count===1) return representative?eventSummary(representative,locale,actionName):auditText('operation',locale)
  if(representative?.entity==='inventory_items'&&representative.action==='create') return auditText('productRegistration',locale)
  // These aggregates cover the whole filtered group; samples alone cannot prove
  // that every event in a batch had the same action or quantity.
  if(group.kind==='stock'&&group.module_count===1&&group.movement_kind) {
    const kind=group.movement_kind
    return auditText(kind==='transfer'?'stockTransfer':kind==='adjustment'?'adjustment':kind,locale)
  }
  if(representative&&customActions.has(representative.action)) return eventSummary(representative,locale,actionName)
  if(representative&&group.entity_count===1&&group.action_count===1&&representative.entity&&entityPlurals[representative.entity]) {
    const key=representative.action==='create'?'batchCreate':representative.action==='update'?'batchUpdates':representative.action==='delete'?'batchDeletes':null
    if(key) return auditText(key,locale,{entity:localized(entityPlurals[representative.entity],locale)})
  }
  if(group.kind==='stock') return auditText('stock',locale)
  return auditText('operation',locale)
}
