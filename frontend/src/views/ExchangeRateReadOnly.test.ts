import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import ExchangeRateManagement from './ExchangeRateManagement.vue'
const mocks = vi.hoisted(() => ({ getHistory: vi.fn(), getSalesAverage: vi.fn(), editHistoricalRate: vi.fn(), deleteHistoricalRate: vi.fn(), loadCurrentRates: vi.fn(), updateRatesAPI: vi.fn() }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ isReseller: true, user: { id: 'restricted', role: 'GERENTE' } }) }))
vi.mock('@/stores/currency', () => ({ useCurrencyStore: () => ({ ...mocks, currentRates: { usd_to_pyg: 6000, usd_to_brl: 5.1, eur_to_usd: 1.2, eur_to_brl: 6.12 } }) }))
vi.mock('@/services/api', () => ({ exchangeRateAPI: mocks }))
let app: App | undefined, root: HTMLDivElement
const flush = async () => { for(let i=0; i<8; i++){ await Promise.resolve(); await nextTick() } }
beforeEach(() => {
  vi.resetAllMocks(); root=document.createElement('div'); document.body.append(root)
  mocks.getHistory.mockResolvedValue({ historical_rates: [{id:'rate',currency_pair:'USD_TO_BRL',rate:5.1,is_active:false,created_at:'2026-11-12T12:00:00Z'}] })
  mocks.getSalesAverage.mockResolvedValue(null)
})
afterEach(() => { app?.unmount(); root.remove() })
it('loads current/history rates, while preventing update/edit/delete handlers from calling the API', async () => {
  app=createApp(ExchangeRateManagement).use(createI18n({legacy:false,locale:'pt',messages:{pt:{}}}));app.mount(root);await flush()
  expect(mocks.loadCurrentRates).toHaveBeenCalledOnce(); expect(mocks.getHistory).toHaveBeenCalledOnce(); expect(mocks.getSalesAverage).toHaveBeenCalledOnce()
  expect(root.textContent).toContain('Acesso de consulta')
  expect(root.querySelector<HTMLButtonElement>('.btn-icon.edit')?.disabled).toBe(true)
  expect(root.querySelector<HTMLButtonElement>('.btn-icon.delete')?.disabled).toBe(true)
  const state=(app as any)._instance.setupState
  state.startEdit({id:'rate'});state.confirmDelete({id:'rate'});await state.performQuickUpdate();await state.saveEditedRate();await state.deleteRate();await flush()
  expect(root.querySelector('.modal-overlay')).toBeNull()
  expect(mocks.updateRatesAPI).not.toHaveBeenCalled();expect(mocks.editHistoricalRate).not.toHaveBeenCalled();expect(mocks.deleteHistoricalRate).not.toHaveBeenCalled()
})
