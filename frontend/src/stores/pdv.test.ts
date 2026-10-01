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
