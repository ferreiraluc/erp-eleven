import { afterEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import Panel from './BonanzaSyncPanel.vue'
const mocks = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn(), loadCurrentRates: vi.fn() }))
vi.mock('@/services/api', () => ({ default: mocks }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ token: 'synthetic', isOwner: true }) }))
vi.mock('@/stores/currency', () => ({ useCurrencyStore: () => mocks }))
let app: App, root: HTMLElement
const flush = async () => { await nextTick(); await nextTick(); await nextTick() }
async function mount() {
  root = document.createElement('div'); document.body.append(root)
  app = createApp(Panel).use(createI18n({ legacy: false, locale: 'pt', messages: { pt: {} } })); app.mount(root); await flush()
}
afterEach(() => { app?.unmount(); root?.remove(); vi.resetAllMocks() })
it('enables the fixed Jebai/Venta integration then refreshes shared quotes', async () => {
  mocks.get.mockResolvedValue({ data: { enabled: false } }); mocks.put.mockResolvedValue({ data: { enabled: true } })
  await mount(); expect(root.textContent).toContain('Jebai · Venta')
  root.querySelector('button')!.click(); await flush()
  expect(mocks.put).toHaveBeenCalledWith('/api/exchange-rates/bonanza', { enabled: true }, expect.anything())
  expect(mocks.loadCurrentRates).toHaveBeenCalledTimes(1)
  expect(root.textContent).toContain('Pausar atualização')
})
it('keeps an update failure visible without claiming rates were applied', async () => {
  mocks.get.mockResolvedValue({ data: { enabled: false } }); mocks.put.mockResolvedValue({ data: { enabled: true, last_error: 'provider_unavailable' } })
  await mount(); root.querySelector('button')!.click(); await flush()
  expect(root.querySelector('[role=alert]')?.textContent).toContain('preservadas')
  expect(mocks.loadCurrentRates).not.toHaveBeenCalled()
})
