import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import i18n from '@/i18n'
import { uiText } from '@/i18n/uiText'
import DashboardView from './DashboardView.vue'

const { auth, getRates, getAlerts, getItems, checkHealth } = vi.hoisted(() => ({
  auth: { user: { id:'user-1',nome:'Lucas',role:'ADMIN' } as {id:string;nome:string;role:string}|null, userName:'Lucas',ownSales:false },
  getRates:vi.fn(),getAlerts:vi.fn(),getItems:vi.fn(),checkHealth:vi.fn(),
}))
vi.mock('@/stores/auth',()=>({useAuthStore:()=>auth}))
vi.mock('@/stores/currency',()=>({useCurrencyStore:()=>({availableCurrencies:[],selectedCurrency:'USD'})}))
vi.mock('vue-router',()=>({useRouter:()=>({push:vi.fn(),replace:vi.fn()})}))
vi.mock('@/services/api',()=>({
  exchangeRateAPI:{getCurrentRates:getRates},
  inventoryAPI:{getAlertsSummary:getAlerts,getItems},healthAPI:{check:checkHealth},
}))
vi.mock('@/components/RastreamentoCard.vue',()=>({default:{render:()=>null}}))
vi.mock('@/components/FolgasCard.vue',()=>({default:{render:()=>null}}))
vi.mock('@/components/dashboard/AddressSummaryCard.vue',()=>({default:{render:()=>null}}))
vi.mock('@/components/dashboard/SalesSummaryCard.vue',()=>({default:{render:()=>null}}))

function deferred<T>() { let resolve!:(value:T)=>void;const promise=new Promise<T>(r=>{resolve=r});return {promise,resolve} }
let app:App|null=null,element:HTMLElement|null=null
function mount() {
  element=document.createElement('div');document.body.append(element)
  app=createApp(DashboardView);app.use(i18n);app.config.globalProperties.$tr=uiText;app.mount(element)
}
function unmount(){app?.unmount();app=null;element?.remove();element=null}
async function settle(){await vi.dynamicImportSettled();await nextTick();await Promise.resolve()}
beforeEach(()=>{
  vi.useFakeTimers();vi.clearAllMocks();localStorage.clear()
  auth.user={id:'user-1',nome:'Lucas',role:'ADMIN'}
  getAlerts.mockResolvedValue({});getItems.mockResolvedValue({items:[]});checkHealth.mockResolvedValue({api:'online',database:'online'})
})
afterEach(()=>{unmount();vi.useRealTimers()})

describe('dashboard lifecycle and session isolation',()=>{
  it('does not start polling or save late exchange rates after unmount',async()=>{
    const rates=deferred<unknown>();getRates.mockReturnValue(rates.promise)
    mount();await settle();expect(getRates).toHaveBeenCalledOnce()
    unmount();rates.resolve({usd_to_pyg:7501,usd_to_brl:5.2,last_updated:'2026-09-30T18:00:00Z'});await settle()
    expect(getAlerts).not.toHaveBeenCalled();expect(getItems).not.toHaveBeenCalled();expect(checkHealth).not.toHaveBeenCalled()
    expect(localStorage.getItem('erp_exchange_rates')).toBeNull()
    expect(vi.getTimerCount()).toBe(0)
    await vi.advanceTimersByTimeAsync(90_000);expect(checkHealth).not.toHaveBeenCalled()
  })

  it('discards a pending response when the authenticated user changes before unmount',async()=>{
    const rates=deferred<unknown>();getRates.mockReturnValue(rates.promise)
    mount();await settle();auth.user={id:'user-2',nome:'Sol',role:'VENDEDOR'}
    rates.resolve({usd_to_pyg:9999});await settle()
    expect(getAlerts).not.toHaveBeenCalled();expect(checkHealth).not.toHaveBeenCalled()
    expect(localStorage.getItem('erp_exchange_rates')).toBeNull()
    unmount();expect(vi.getTimerCount()).toBe(0)
  })

  it('clears active timers even when inventory and health responses finish later',async()=>{
    const health=deferred<unknown>(),items=deferred<unknown>(),alerts=deferred<unknown>()
    getRates.mockResolvedValue({usd_to_pyg:7500});checkHealth.mockReturnValue(health.promise)
    getAlerts.mockReturnValue(alerts.promise);getItems.mockReturnValue(items.promise)
    mount();await settle();expect(checkHealth).toHaveBeenCalledOnce();expect(getItems).toHaveBeenCalledOnce()
    unmount();health.resolve({api:'online',database:'online'});items.resolve({items:[]});alerts.resolve({});await settle()
    expect(vi.getTimerCount()).toBe(0)
    await vi.advanceTimersByTimeAsync(90_000);expect(checkHealth).toHaveBeenCalledOnce()
  })
})
