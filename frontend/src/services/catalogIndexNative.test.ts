import { expect, it, vi } from 'vitest'
const mocks = vi.hoisted(() => ({ prepare: vi.fn(), search: vi.fn() }))
vi.mock('@capacitor/core', () => ({ Capacitor: { isNativePlatform: () => true } }))
vi.mock('./offlineCatalog', () => ({ prepareOfflineCatalog: mocks.prepare, searchOfflineCatalog: mocks.search }))
vi.mock('./api', () => ({ default: { get: vi.fn() } }))
vi.mock('./sessionStorage', () => ({ storedToken: () => 'native-session', tokenIsCurrent: () => true }))
import { prepareCatalogIndex, searchDeviceCatalog } from './catalogIndex'
it('reuses the native snapshot worker but leaves online PDV results provisional', async () => {
  mocks.search.mockResolvedValue({ items: [{ id: 'one', stock_loja: 3, stock_deposito: 8, current_stock: 11, sale_price: 80, sale_currency: 'USD' }] })
  await prepareCatalogIndex('lucas')
  expect(mocks.prepare).toHaveBeenCalledExactlyOnceWith({ userId: 'lucas', token: 'native-session' })
  const rows = await searchDeviceCatalog('camiseta')
  expect(rows[0]).toMatchObject({ catalog_cached: true, stock_loja: null, stock_deposito: null, current_stock: null, sale_price: 80 })
})
