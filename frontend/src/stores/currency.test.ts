import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { reactive } from 'vue'
import { useCurrencyStore } from './currency'
const mocks = vi.hoisted(() => ({ get: vi.fn(), update: vi.fn(), auth: {} as any }))
vi.mock('@/services/api', () => ({ exchangeRateAPI: { getCurrentRates: mocks.get, quickUpdate: mocks.update } }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))
const rates = { usd_to_pyg: '6000.0000', usd_to_brl: '5.1000', eur_to_usd: '1.2000', eur_to_brl: '6.1200', last_updated: '2026-10-12T12:00:00Z' }
beforeEach(() => { vi.resetAllMocks(); localStorage.clear(); setActivePinia(createPinia()); mocks.auth = reactive({ user: { id: '1', nome: 'Lucas', role: 'ADMIN' }, token: 'test' }); mocks.get.mockResolvedValue(rates) })
it('normalizes decimal strings once, shares concurrent reads and migrates the cache', async () => {
  localStorage.setItem('erp_exchange_rates', JSON.stringify({ 'G$': '5500' }))
  const store = useCurrencyStore()
  expect(store.exchangeRates['G$']).toBe(5500)
  await Promise.all([store.loadCurrentRates(), store.loadCurrentRates()])
  expect(mocks.get).toHaveBeenCalledOnce()
  expect(store.exchangeRates['G$']).toBe(6000)
  expect(store.exchangeRates['R$']).toBe(5.1)
  expect(store.convertFromUSD(2, 'EUR')).toBeCloseTo(2 / 1.2)
  expect(store.currentRates?.eur_to_brl).toBe(6.12)
  expect(localStorage.getItem('erp_exchange_rates')).toBeNull()
  expect(JSON.parse(localStorage.getItem('erp_rates')!)['G$']).toBe(6000)
})
it('rejects invalid rates and reports failed refresh after saving', async () => {
  const store = useCurrencyStore(); await store.loadCurrentRates()
  mocks.get.mockResolvedValueOnce({ ...rates, usd_to_pyg: 'NaN', eur_to_usd: '-1' })
  await store.loadCurrentRates(); expect(store.exchangeRates['G$']).toBe(0); expect(store.exchangeRates.EUR).toBe(0)
  mocks.get.mockRejectedValueOnce(new Error('offline'))
  await expect(store.updateRatesAPI({ usd_to_brl: 5.2 })).rejects.toThrow('Taxas salvas')
  expect(store.error).toBeTruthy()
})
it('does not repopulate shared rates after logout', async () => {
  let finish!: (value: unknown) => void
  mocks.get.mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  const store = useCurrencyStore(), request = store.loadCurrentRates()
  mocks.auth.user = null; mocks.auth.token = null; finish(rates)
  expect(await request).toBe(false)
  expect(store.currentRates).toBeNull(); expect(localStorage.getItem('erp_rates')).toBeNull()
})
