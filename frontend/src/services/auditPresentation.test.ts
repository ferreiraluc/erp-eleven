import { describe, expect, it } from 'vitest'
import type { AuditEvent, AuditGroup } from './access'
import { auditFieldName, auditText, eventSummary, groupTitle, productLabel, saleFacts, stockBalanceText } from './auditPresentation'

const entry=(changes:Record<string,unknown>,action='create')=>({entity:'stock_movements',action,changes} as AuditEvent)
const label=(action:string)=>action==='delete'?'Excluiu':action

describe('Audit operation descriptions',()=>{
  it('distinguishes a sale stock decrease, a return and a transfer without counting transfer as stock loss',()=>{
    expect(eventSummary(entry({_context:{movement:{quantity_before:8,quantity_after:6,location_from:'loja'}}}),'pt',label)).toBe('Saída de estoque · 2 un. · Loja')
    expect(eventSummary(entry({_context:{movement:{quantity_before:6,quantity_after:8,location_to:'deposito'}}}),'pt',label)).toBe('Entrada de estoque · 2 un. · Depósito')
    expect(eventSummary(entry({_context:{movement:{movement_type:'transfer',quantity:3,quantity_before:8,quantity_after:8,location_from:'deposito',location_to:'loja'}}}),'pt',label)).toBe('Transferência de estoque · 3 un. · Depósito → Loja')
  })
  it('uses historical numeric evidence without inventing location and does not describe deleted history as a new stock decrease',()=>{
    const changes={quantity_before:{before:null,after:8},quantity_after:{before:null,after:5}}
    expect(eventSummary(entry(changes),'pt',label)).toBe('Saída de estoque · 3 un. · local não informado')
    expect(stockBalanceText(entry(changes),'pt')).toBe('Estoque total: 8 → 5')
    expect(eventSummary(entry(changes,'delete'),'pt',label)).toBe('Exclusão de movimentação de estoque')
  })
  it('displays separate store and warehouse balances only when the historical local balances were captured',()=>{
    const event=entry({_context:{movement:{quantity_before:8,quantity_after:8,stock_loja_before:0,stock_loja_after:3}}})
    expect(stockBalanceText(event,'pt')).toBe('Loja: 0 → 3 · Depósito: 8 → 5')
  })
  it('shows the immutable product name/code and translates movement facts',()=>{
    const event=entry({_context:{product:{name:'Camiseta',code:'INV-ABC12'},movement:{quantity_before:1,quantity_after:0,location_from:'loja'}}})
    expect(productLabel(event)).toBe('Camiseta · INV-ABC12')
    expect(eventSummary(event,'es',label)).toBe('Salida de inventario · 1 un. · Tienda')
    expect(eventSummary(event,'en',label)).toBe('Stock removal · 1 units · Store')
  })
})


it('describes confirmed grade links using the reviewed destination instead of internal receipt hashes',()=>{
  const event={...entry({target_group_key:'Polo Eleven',item_ids:['one','two'],preview_hash:'internal'}),entity:'inventory_grade_links',action:'grade_link'}
  expect(eventSummary(event,'pt',label)).toBe('Vinculou 2 produtos à grade Polo Eleven')
  expect(eventSummary(event,'es',label)).toBe('Vinculó 2 productos al grupo Polo Eleven')
})

const event=(entity:string,action:string,changes:Record<string,unknown>={})=>({...entry(changes,action),entity,actor_name:'Lucas'})
const grouped=(representative:AuditEvent,extra:Partial<AuditGroup>={})=>({key:'request:one',kind:'operation',event_count:1,sale_id:null,sale_code:null,first_at:'2026-11-09T01:08:25Z',last_at:'2026-11-09T01:08:25Z',actor_name:'Lucas',actor_count:1,module:representative.module,samples:[representative],summary_event:representative,...extra} as AuditGroup)

describe('Objective historical audit labels',()=>{
  it('describes the legacy customer name change, ignoring metadata without reconstructing private values',()=>{
    const legacy=event('clientes','update',{id:{changed:true},nome:{changed:true},updated_at:{changed:true}})
    expect(eventSummary(legacy,'pt',label)).toBe('Alteração de nome do cliente')
    expect(groupTitle(grouped(legacy),'pt',label)).toBe('Alteração de nome do cliente')
    expect(eventSummary(legacy,'es',label)).toBe('Cambio de nombre del cliente')
    expect(eventSummary(legacy,'en',label)).toBe('name changed for customer')
    expect(legacy.changes.nome).toEqual({changed:true})
    expect(auditFieldName('nome','pt')).toBe('Nome')
    expect(auditText('record','pt')).toBe('1 registro')
  })
  it('distinguishes creation and deletion even when a product carries stock fields',()=>{
    const changes={name:{changed:true},stock_loja:{before:null,after:1},current_stock:{before:null,after:2}}
    expect(eventSummary(event('inventory_items','create',changes),'pt',label)).toBe('Cadastro de produto')
    expect(eventSummary(event('inventory_items','delete',changes),'pt',label)).toBe('Exclusão de produto')
    expect(eventSummary(event('clientes','create',{nome:{changed:true}}),'pt',label)).toBe('Cadastro de cliente')
    expect(eventSummary(event('clientes','delete',{nome:{changed:true}}),'pt',label)).toBe('Exclusão de cliente')
    expect(eventSummary(event('inventory_items','update',{color:{changed:true}}),'pt',label)).toBe('Alteração de cor do produto')
    expect(eventSummary(event('clientes','update',{unknown_private_field:{changed:true}}),'pt',label)).toBe('Alteração de cliente')
  })
  it('shows the captured seller and historical USD total without substituting the editing actor',()=>{
    const sale=event('pdv_sales','create',{_context:{sale:{seller_name:'Sol',total_gs:'480000',usd_rate_gs:'6000'}}})
    expect(groupTitle(grouped(sale,{kind:'sale',sale_code:'ABC123'}),'pt',label)).toBe('Venda · Sol · U$ 80,00')
    expect(saleFacts(sale,'pt')).toEqual({seller:'Sol',amount:'U$ 80,00'})
    expect(groupTitle(grouped({...sale,action:'update'},{kind:'sale'}),'pt',label)).toBe('Venda · Sol · U$ 80,00')
    const correction={...sale,action:'pdv_return'}
    expect(groupTitle(grouped(correction,{kind:'sale'}),'pt',()=> 'Devolução parcial')).toBe('Devolução parcial · Sol · Total da venda: U$ 80,00')
    expect(eventSummary(correction,'pt',()=> 'Devolução parcial')).toBe('Devolução parcial')
  })
  it('preserves zero and missing historical currency data without inventing dollar conversion or a seller',()=>{
    expect(saleFacts(event('pdv_sales','create',{_context:{sale:{total_gs:0,usd_rate_gs:6000}}}),'pt')).toEqual({seller:'',amount:'U$ 0,00'})
    expect(saleFacts(event('pdv_sales','create',{total_gs:{after:'480000'}}),'pt')).toEqual({seller:'',amount:'G$ 480.000'})
    expect(saleFacts(event('pdv_sales','update',{_context:{sale:{total_gs:'0',usd_rate_gs:'0'}}}),'pt').amount).toBe('G$ 0')
    expect(saleFacts(event('pdv_payments','create',{total_gs:{after:150000}}),'pt').amount).toBe('')
    expect(saleFacts(event('pdv_sales','create',{total_gs:{changed:true}}),'pt').amount).toBe('')
    expect(saleFacts(event('pdv_sales','create',{_context:{sale:{total_gs:'',usd_rate_gs:'6000'}}}),'pt').amount).toBe('')
    expect(groupTitle(grouped(event('pdv_sales','create'),{kind:'sale'}),'pt',label)).toBe('Venda')
  })
  it('keeps operational sales separate and uses their recorded original currency',()=>{
    const operational=event('vendas','create',{valor_bruto:{after:'80'},moeda:{after:'U$'}})
    expect(eventSummary(operational,'pt',label)).toBe('Cadastro de venda operacional · U$ 80,00')
    expect(saleFacts(operational,'pt')).toEqual({seller:'',amount:''})
    expect(eventSummary(event('vendas','update',{descricao_produto:{changed:true},_context:{operational_sale:{seller_name:'Junior',amount:'80',currency:'R$'}}}),'pt',label)).toBe('Alteração de venda operacional · Junior · R$ 80,00')
  })
  it('uses full-group facts for stock titles, never inferring a whole batch from a preview',()=>{
    const movement=entry({_context:{movement:{quantity_before:5,quantity_after:3,location_from:'loja'}}})
    const partial=grouped(movement,{kind:'stock',event_count:20})
    expect(groupTitle(partial,'pt',label)).toBe('Operação de estoque')
    expect(groupTitle({...partial,module_count:1,movement_kind:'exit'},'pt',label)).toBe('Saída de estoque')
    expect(groupTitle({...partial,module_count:2,movement_kind:'exit'},'pt',label)).toBe('Operação de estoque')
    expect(groupTitle({...partial,module_count:1,movement_kind:'transfer'},'pt',label)).toBe('Transferência de estoque')
    expect(groupTitle({...partial,module_count:1,movement_kind:null},'pt',label)).toBe('Operação de estoque')
    expect(groupTitle({...partial,summary_event:event('inventory_items','create'),module_count:1,movement_kind:'entry'},'pt',label)).toBe('Cadastro de produto')
  })
  it('does not label every customer in a mixed update with a sample name change',()=>{
    const customer=event('clientes','update',{nome:{changed:true}})
    const batch=grouped(customer,{event_count:10,entity_count:1,action_count:1,module_count:1})
    expect(groupTitle(batch,'pt',label)).toBe('Alterações de clientes')
    expect(groupTitle({...batch,entity_count:2},'pt',label)).toBe('Operação confirmada')
  })
  it('keeps access and conditional order events distinct from stock sales',()=>{
    expect(eventSummary(event('auth','login'),'pt',label)).toBe('Login')
    expect(eventSummary(event('auth','logout'),'pt',label)).toBe('Logout')
    expect(eventSummary(event('auth','login_failed'),'pt',label)).toBe('Tentativa de login recusada')
    expect(eventSummary(event('pedidos','order_conditional_dispatch'),'pt',label)).toBe('Saída de peças em condicional')
    expect(eventSummary(event('pedidos','order_conditional_return'),'pt',label)).toBe('Devolução de peças em condicional')
  })
})
