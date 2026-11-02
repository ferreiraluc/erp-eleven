import { describe, expect, it } from 'vitest'
import type { AuditEvent } from './access'
import { eventSummary, productLabel, stockBalanceText } from './auditPresentation'

const entry=(changes:Record<string,unknown>,action='create')=>({entity:'stock_movements',action,changes} as AuditEvent)
const label=(action:string)=>action==='delete'?'Excluiu':action

describe('Audit operation descriptions',()=>{
  it('distinguishes a sale stock decrease, a return and a transfer without counting transfer as stock loss',()=>{
    expect(eventSummary(entry({_context:{movement:{quantity_before:8,quantity_after:6,location_from:'loja'}}}),'pt',label)).toBe('Diminuiu 2 un. em Loja')
    expect(eventSummary(entry({_context:{movement:{quantity_before:6,quantity_after:8,location_to:'deposito'}}}),'pt',label)).toBe('Aumentou 2 un. em Depósito')
    expect(eventSummary(entry({_context:{movement:{movement_type:'transfer',quantity:3,quantity_before:8,quantity_after:8,location_from:'deposito',location_to:'loja'}}}),'pt',label)).toBe('Transferiu 3 un. de Depósito para Loja')
  })
  it('uses historical numeric evidence without inventing location and does not describe deleted history as a new stock decrease',()=>{
    const changes={quantity_before:{before:null,after:8},quantity_after:{before:null,after:5}}
    expect(eventSummary(entry(changes),'pt',label)).toBe('Diminuiu 3 un. em local não informado')
    expect(stockBalanceText(entry(changes),'pt')).toBe('Estoque total: 8 → 5')
    expect(eventSummary(entry(changes,'delete'),'pt',label)).toBe('Excluiu · Movimentação de estoque')
  })
  it('displays separate store and warehouse balances only when the historical local balances were captured',()=>{
    const event=entry({_context:{movement:{quantity_before:8,quantity_after:8,stock_loja_before:0,stock_loja_after:3}}})
    expect(stockBalanceText(event,'pt')).toBe('Loja: 0 → 3 · Depósito: 8 → 5')
  })
  it('shows the immutable product name/code and translates movement facts',()=>{
    const event=entry({_context:{product:{name:'Camiseta',code:'INV-ABC12'},movement:{quantity_before:1,quantity_after:0,location_from:'loja'}}})
    expect(productLabel(event)).toBe('Camiseta · INV-ABC12')
    expect(eventSummary(event,'es',label)).toBe('Disminuyó 1 un. en Tienda')
    expect(eventSummary(event,'en',label)).toBe('Removed 1 units from Store')
  })
})
