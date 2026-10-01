import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from './auth'
import { usePdvStore } from './pdv'
import { pdvAPI, type User, type PdvSaleResponse, type PdvClienteResponse } from '@/services/api'

function account(name: string, scope: 'all'|'own' = 'own'): User {
  return {id:name,nome:name,email:name.toLowerCase()+'@eleven.com',role:name==='Lucas'?'ADMIN':'GERENTE',ativo:true,
    sales_scope:scope,sales_seller:name,vendedor_id:name,must_change_password:false,created_at:'',updated_at:''}
}
function login(name: string, scope: 'all'|'own' = 'own') {
  const auth=useAuthStore();auth.user=account(name,scope);auth.token=`token-${name}`;auth.status='authenticated';return auth
}
const item = { item_id:null,item_name:'Private draft',item_sku:null,item_category:null,item_size:null,item_color:null,
  quantity:1,unit_price_gs:100,original_price_gs:null,original_price:100,sale_currency:'PYG',image_data:null,
  discount_gs:0,is_avulso:true,location:'loja' }
function sale(id: string): PdvSaleResponse { return {id,vendedor_id:'Lucas',cliente_id:null,cliente_nome:'Private customer',subtotal_gs:100,
  desconto_gs:0,total_gs:100,status:'completed',stock_applied:false,notas:null,items:[],payments:[],created_at:''} }
function client(balance: number|null): PdvClienteResponse { return {id:'client-1',nome:'Customer',doc:null,telefone:null,email:null,
  tipo:'atacadista',limite_fiado_gs:1000,saldo_fiado_gs:balance,notas:null,ativo:true,created_at:''} }
function deferred<T>() { let resolve!:(value:T)=>void; const promise=new Promise<T>(r=>{resolve=r});return {promise,resolve} }
beforeEach(()=>{setActivePinia(createPinia());localStorage.clear();sessionStorage.clear()})

describe('PDV session isolation',()=>{
  it('clears drafts, payments, receipts and cached client balances immediately on logout',()=>{
    const auth=login('Lucas','all'),pdv=usePdvStore();pdv.addItem(item)
    pdv.clienteNome='Private customer';pdv.clienteId='client-1';pdv.notas='Private note';pdv.discountGs=10
    pdv.lastSale=sale('sale-1');pdv.clients=[client(900)]
    pdv.addPayment({method:'cash_gs',currency:'GS',amount_original:100,exchange_rate:1,amount_gs:100,cambista_id:null,reference:null,label:'Cash'})
    auth.expire()
    expect(pdv.cart).toEqual([]);expect(pdv.payments).toEqual([]);expect(pdv.lastSale).toBeNull();expect(pdv.clients).toEqual([])
    expect(pdv.clienteNome).toBeNull();expect(pdv.clienteId).toBeNull();expect(pdv.notas).toBe('');expect(pdv.discountGs).toBe(0)
    login('Sol');expect(usePdvStore().cart).toEqual([])
  })

  it('clears financial data when the same user receives a new session or restricted scope',()=>{
    const auth=login('Lucas','all'),pdv=usePdvStore();pdv.addItem(item);pdv.clients=[client(900)]
    auth.token='new-session';expect(pdv.cart).toEqual([]);expect(pdv.clients).toEqual([])
    pdv.clients=[client(900)];auth.user={...auth.user!,sales_scope:'own'}
    expect(pdv.clients).toEqual([])
  })

  it('preserves a draft during ordinary permission revalidation of the same session',()=>{
    const auth=login('Sol'),pdv=usePdvStore();pdv.addItem(item)
    auth.user={...auth.user!}
    expect(pdv.cart).toHaveLength(1)
    expect(pdv.cart[0].item_name).toBe('Private draft')
  })

  it('does not overwrite a new account cart or loading state with an old completed sale',async()=>{
    const old=deferred<PdvSaleResponse>(),current=deferred<PdvSaleResponse>()
    vi.spyOn(pdvAPI,'createSale').mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise)
    const auth=login('Lucas','all'),pdv=usePdvStore();pdv.addItem(item);const first=pdv.completeSale()
    auth.expire();login('Sol');pdv.addItem({...item,item_name:'Sol draft'});const second=pdv.completeSale()
    old.resolve(sale('committed-old'));expect((await first).id).toBe('committed-old')
    expect(pdv.lastSale).toBeNull();expect(pdv.cart[0].item_name).toBe('Sol draft');expect(pdv.loading).toBe(true)
    current.resolve({...sale('committed-current'),vendedor_id:'Sol'});await second
    expect(pdv.lastSale?.id).toBe('committed-current');expect(pdv.cart).toEqual([]);expect(pdv.loading).toBe(false)
  })

  it('ignores old full-balance and out-of-order client lookups',async()=>{
    const old=deferred<PdvClienteResponse[]>(),earlier=deferred<PdvClienteResponse[]>(),latest=deferred<PdvClienteResponse[]>()
    vi.spyOn(pdvAPI,'getClients').mockReturnValueOnce(old.promise).mockReturnValueOnce(earlier.promise).mockReturnValueOnce(latest.promise)
    const auth=login('Lucas','all'),pdv=usePdvStore();const first=pdv.loadClients()
    auth.expire();login('Sol');const second=pdv.loadClients('older-search'),third=pdv.loadClients('latest-search')
    latest.resolve([client(null)]);await third;old.resolve([client(900)]);await first
    earlier.resolve([{...client(null),nome:'Older search'}]);await second
    expect(pdv.clients).toEqual([client(null)])
  })
})

const snapshot = { id: 'catalog-1', current_stock: 8, stock_loja: 3, stock_deposito: 5, is_active: true }
const catalog = { ...item, item_id: snapshot.id, is_avulso: false }
const payment = { method:'cash_gs',currency:'GS',amount_original:100,exchange_rate:1,amount_gs:100,cambista_id:null,reference:null,label:'Cash' }
describe('PDV stock conservation', () => {
  it.each([0, -1, 1.5, NaN, Infinity, 10_000_000])('rejects invalid catalog quantity %s without changing a valid cart', quantity => {
    login('Lucas'); const pdv = usePdvStore(); pdv.addItem(catalog, snapshot)
    expect(() => pdv.addItem({ ...catalog, quantity }, snapshot)).toThrow('catalogQuantity')
    expect(() => pdv.updateItemQty(pdv.cart[0].id, quantity)).toThrow('catalogQuantity')
    expect(pdv.cart[0].quantity).toBe(1)
  })
  it('merges same item/price/location using requested quantity but never merges distinct locations', () => {
    login('Lucas'); const pdv = usePdvStore()
    pdv.addItem(catalog, snapshot); pdv.addItem({ ...catalog, quantity: 2 })
    pdv.addItem({ ...catalog, location: 'deposito', quantity: 4 })
    expect(pdv.cart.map(line => [line.location, line.quantity])).toEqual([['loja', 3], ['deposito', 4]])
    expect(() => pdv.addItem(catalog)).toThrow('insufficientStock')
    expect(pdv.availableStock(snapshot.id, 'loja')).toBe(0)
    expect(pdv.availableStock(snapshot.id, 'deposito')).toBe(1)
  })
  it('sums all price variants before accepting additions or updates and releases removed quantities', () => {
    login('Lucas'); const pdv = usePdvStore(); pdv.addItem(catalog, snapshot)
    pdv.addItem({ ...catalog, unit_price_gs: 120, quantity: 2 })
    expect(pdv.cart).toHaveLength(2)
    expect(() => pdv.addItem({ ...catalog, unit_price_gs: 130 })).toThrow('insufficientStock')
    expect(() => pdv.updateItemQty(pdv.cart[0].id, 2)).toThrow('insufficientStock')
    expect(pdv.cart[0].quantity).toBe(1)
    pdv.removeItem(pdv.cart[1].id); pdv.updateItemQty(pdv.cart[0].id, 3)
    expect(pdv.cart[0].quantity).toBe(3)
  })
  it.each([
    { current_stock: 0, stock_loja: 0, stock_deposito: 0 },
    { current_stock: 8, stock_loja: 0, stock_deposito: 8 },
    { current_stock: 8, stock_loja: 3, stock_deposito: null },
    { current_stock: 9, stock_loja: 3, stock_deposito: 5 },
    { current_stock: 8, stock_loja: -1, stock_deposito: 9 },
  ])('blocks zero/unavailable/invalid local stock %j', balances => {
    login('Lucas'); const pdv = usePdvStore()
    expect(() => pdv.addItem(catalog, { ...snapshot, ...balances })).toThrow()
    expect(pdv.cart).toEqual([])
  })
  it('rejects absent product, unknown snapshot, invalid local and inactive product', () => {
    login('Lucas'); const pdv = usePdvStore()
    expect(() => pdv.addItem({ ...catalog, item_id: null })).toThrow('missingProduct')
    expect(() => pdv.addItem(catalog)).toThrow('unknownStock')
    expect(() => pdv.addItem({ ...catalog, location: 'other' }, snapshot)).toThrow('invalidLocation')
    expect(() => pdv.addItem(catalog, { ...snapshot, is_active: false })).toThrow('inactiveProduct')
  })
  it('accepts positive avulso fractions exactly up to three decimals without stock movement hints', () => {
    login('Lucas'); const pdv = usePdvStore()
    pdv.addItem({ ...item, quantity: .125 }); pdv.updateItemQty(pdv.cart[0].id, .001)
    expect(pdv.cart[0].quantity).toBe(.001)
    for (const quantity of [0, -1, .0001, 1.1234, NaN, Infinity, 10_000_000]) {
      expect(() => pdv.addItem({ ...item, quantity })).toThrow('manualQuantity')
    }
    expect(pdv.cart).toHaveLength(1)
  })
  it('keeps cart and payments on 409, accepts only a manual retry and blocks concurrent checkout', async () => {
    const api = vi.spyOn(pdvAPI, 'createSale').mockRejectedValueOnce({ response: { status: 409, data: { detail: 'Saldo insuficiente' } } })
    login('Lucas'); const pdv = usePdvStore(); pdv.addItem(catalog, snapshot); pdv.addPayment(payment)
    await expect(pdv.completeSale()).rejects.toMatchObject({ response: { status: 409 } })
    expect(pdv.cart).toHaveLength(1); expect(pdv.payments).toHaveLength(1); expect(pdv.checkoutUncertain).toBe(false)
    expect(api).toHaveBeenCalledTimes(1)
    const pending = deferred<PdvSaleResponse>(); api.mockReturnValueOnce(pending.promise)
    const first = pdv.completeSale()
    await expect(pdv.completeSale()).rejects.toThrow('busy')
    expect(() => pdv.updateItemQty(pdv.cart[0].id, 2)).toThrow('busy')
    expect(api).toHaveBeenCalledTimes(2)
    pending.resolve(sale('success')); await first
    expect(pdv.cart).toEqual([]); expect(pdv.payments).toEqual([])
  })
  it.each([new Error('timeout'), { response: { status: 500 } }])('blocks retry after an uncertain result until explicit draft clearing', async error => {
    const api = vi.spyOn(pdvAPI, 'createSale').mockRejectedValueOnce(error)
    login('Lucas'); const pdv = usePdvStore(); pdv.addItem(catalog, snapshot); pdv.addPayment(payment)
    await expect(pdv.completeSale()).rejects.toBe(error)
    expect(pdv.checkoutUncertain).toBe(true); expect(pdv.cart).toHaveLength(1); expect(pdv.payments).toHaveLength(1)
    await expect(pdv.completeSale()).rejects.toThrow('uncertain')
    expect(api).toHaveBeenCalledTimes(1)
    pdv.clearCart(); expect(pdv.checkoutUncertain).toBe(false)
  })
  it('revalidates all lines against the latest read snapshot before checkout without posting invalid stock', async () => {
    const api = vi.spyOn(pdvAPI, 'createSale')
    login('Lucas'); const pdv = usePdvStore(); pdv.addItem(catalog, snapshot)
    pdv.rememberStock([{ ...snapshot, current_stock: 5, stock_loja: 0 }])
    await expect(pdv.completeSale()).rejects.toThrow('insufficientStock')
    expect(api).not.toHaveBeenCalled(); expect(pdv.cart).toHaveLength(1); expect(pdv.checkoutUncertain).toBe(false)
  })
  it('does not poison a new session with an old uncertain request or leak stock snapshots', async () => {
    let reject!: (error: unknown) => void
    vi.spyOn(pdvAPI, 'createSale').mockReturnValueOnce(new Promise((_resolve, no) => { reject = no }))
    const auth = login('Lucas'); const pdv = usePdvStore(); pdv.addItem(catalog, snapshot)
    const request = pdv.completeSale(); const failed = expect(request).rejects.toThrow('timeout')
    auth.expire(); login('Sol'); pdv.addItem(item)
    expect(pdv.availableStock(snapshot.id, 'loja')).toBeNull()
    reject(new Error('timeout')); await failed
    expect(pdv.checkoutUncertain).toBe(false); expect(pdv.cart[0].is_avulso).toBe(true)
  })
})
