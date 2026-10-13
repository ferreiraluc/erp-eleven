import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createPinia } from 'pinia'
import ExchangeRateModal from './ExchangeRateModal.vue'
const mocks = vi.hoisted(() => ({ get: vi.fn(), update: vi.fn() }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: { id: '1', nome: 'Lucas', role: 'ADMIN' } }) }))
vi.mock('@/services/api', () => ({ exchangeRateAPI: { getCurrentRates: mocks.get, quickUpdate: mocks.update } }))
let app: App, root: HTMLDivElement
const rates = { usd_to_pyg: '6000.0000', usd_to_brl: '5.1000', eur_to_usd: '1.2000', eur_to_brl: '6.1200' }
async function tick() { for (let i=0;i<5;i++) { await Promise.resolve(); await nextTick() } }
beforeEach(() => { vi.resetAllMocks(); localStorage.clear(); mocks.get.mockResolvedValue(rates); root=document.createElement('div'); document.body.append(root) })
afterEach(() => { app?.unmount(); root.remove() })
it('loads real values in a teleported modal and saves comma decimals without inventing EUR rates', async () => {
  const close=vi.fn(); app=createApp(ExchangeRateModal,{onClose:close}).use(createPinia()); app.mount(root)
  await tick()
  const dialog=document.querySelector('[role=dialog]')!
  expect(root.contains(dialog)).toBe(false)
  const input=Array.from(dialog.querySelectorAll('input')).find(el=>el.getAttribute('aria-label')==='🇺🇸 U$ → 🇧🇷 R$')!
  expect(input.value).toBe('5,1')
  input.focus();input.value='5,25';input.dispatchEvent(new Event('input',{bubbles:true}));await tick()
  expect(input.value).toBe('5,25')
  dialog.querySelector('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await tick()
  expect(mocks.update).toHaveBeenCalledWith(expect.objectContaining({usd_to_brl:5.25}))
  expect(mocks.update.mock.calls[0][0]).not.toHaveProperty('eur_to_usd')
  expect(close).toHaveBeenCalledOnce()
})
it('shows a recoverable load error, without enabling save with cached defaults', async () => {
  mocks.get.mockRejectedValueOnce(new Error('offline'))
  app=createApp(ExchangeRateModal).use(createPinia());app.mount(root);await tick()
  expect(document.querySelector('button[type=submit]')?.hasAttribute('disabled')).toBe(true)
  expect(document.body.textContent).toContain('Tentar novamente')
  const retry=Array.from(document.querySelectorAll('button')).find(b=>b.textContent?.includes('Tentar novamente'))!
  retry.click();await tick()
  expect(document.querySelector('input')?.value).toBe('6000')
})
