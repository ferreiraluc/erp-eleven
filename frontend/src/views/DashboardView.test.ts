import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createPinia } from 'pinia'
import i18n from '@/i18n'
import { uiText } from '@/i18n/uiText'
import DashboardView from './DashboardView.vue'

const { auth, getRates, getAlerts, getItems, checkHealth, mountPrivate, mountBell } = vi.hoisted(() => ({
  auth: { user: { id:'user-1',nome:'Lucas',role:'ADMIN' } as {id:string;nome:string;role:string}|null, userName:'Lucas',ownSales:false,isReseller:false },
  getRates:vi.fn(),getAlerts:vi.fn(),getItems:vi.fn(),checkHealth:vi.fn(),mountPrivate:vi.fn(),mountBell:vi.fn(),
}))
vi.mock('@/stores/auth',()=>({useAuthStore:()=>auth}))
vi.mock('vue-router',()=>({useRouter:()=>({push:vi.fn(),replace:vi.fn()})}))
vi.mock('@/services/api',()=>({
  exchangeRateAPI:{getCurrentRates:getRates},
  inventoryAPI:{getAlertsSummary:getAlerts,getItems},healthAPI:{check:checkHealth},
}))
vi.mock('@/components/RastreamentoCard.vue',()=>({default:{setup:()=>{mountPrivate('tracking');return()=>null}}}))
vi.mock('@/components/FolgasCard.vue',()=>({default:{setup:()=>{mountPrivate('days-off');return()=>null}}}))
vi.mock('@/components/notifications/NotificationBell.vue',()=>({default:{setup:()=>{mountBell();return()=>null}}}))
vi.mock('@/components/dashboard/AddressSummaryCard.vue',()=>({default:{setup:()=>{mountPrivate('addresses');return()=>null}}}))
vi.mock('@/components/dashboard/SalesSummaryCard.vue',()=>({default:{setup:()=>{mountPrivate('sales');return()=>null}}}))

function deferred<T>() { let resolve!:(value:T)=>void;const promise=new Promise<T>(r=>{resolve=r});return {promise,resolve} }
let app:App|null=null,element:HTMLElement|null=null
function mount() {
  element=document.createElement('div');document.body.append(element)
  app=createApp(DashboardView);app.use(createPinia());app.use(i18n);app.config.globalProperties.$tr=uiText;app.mount(element)
}
function unmount(){app?.unmount();app=null;element?.remove();element=null}
async function settle(){await vi.dynamicImportSettled();await nextTick();await Promise.resolve()}
beforeEach(()=>{
  vi.useFakeTimers();vi.clearAllMocks();localStorage.clear()
  auth.user={id:'user-1',nome:'Lucas',role:'ADMIN'}
  auth.isReseller=false
  getAlerts.mockResolvedValue({});getItems.mockResolvedValue({items:[]});checkHealth.mockResolvedValue({api:'online',database:'online'})
})
afterEach(()=>{unmount();vi.useRealTimers()})

describe('dashboard lifecycle and session isolation',()=>{
  it('mounts only inventory, exchange and personal notifications for a reseller',async()=>{
    auth.isReseller=true
    getRates.mockResolvedValue({usd_to_pyg:7500,usd_to_brl:5.2})
    mount();await settle()
    expect(getRates).toHaveBeenCalledOnce();expect(getAlerts).toHaveBeenCalledOnce();expect(getItems).toHaveBeenCalledOnce()
    expect(mountPrivate).not.toHaveBeenCalled();expect(mountBell).toHaveBeenCalledOnce()
    expect(checkHealth).not.toHaveBeenCalled()
    expect(element?.querySelector('.inv-card')).not.toBeNull()
    expect(element?.querySelector('.exchange-rate-compact')).not.toBeNull()
    expect(element?.querySelector('.inv-add-btn')).toBeNull()
    expect(element?.querySelector('.quick-strip-card')).toBeNull()
    expect(element?.querySelector('.edit-rate-btn-compact')).toBeNull()
    expect(element?.querySelector('.operation-summary-grid')).toBeNull()
    await vi.advanceTimersByTimeAsync(60_000);expect(checkHealth).not.toHaveBeenCalled()
  })
  it('does not start page polling or dependent requests after unmount',async()=>{
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
