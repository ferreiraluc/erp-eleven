import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import InventoryListView from './InventoryListView.vue'
import { useInventoryStore } from '@/stores/inventory'
import type { InventoryItem } from '@/services/api'

const api = vi.hoisted(() => ({ getItems: vi.fn(), getGroups: vi.fn(), getAlertsSummary: vi.fn(), getSuppliers: vi.fn(), getDistinctValues: vi.fn() }))
const auth = vi.hoisted(() => ({ userRole: 'ADMIN', isOwner: false }))
vi.mock('@/services/api', () => ({ inventoryAPI: { ...api, getItemPhotos: async () => ({ additional_images: [] }) }, ocrAPI: {} }))
vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))
vi.mock('@/components/inventory/InventoryCountListModal.vue', () => ({ default: {
  props: ['itemIds'], emits: ['close'], template: '<section role="dialog" class="count-modal-test"><span>{{ itemIds.join(",") }}</span><button @click="$emit(\'close\')">Fechar lista</button></section>',
} }))

let app: App | undefined, root: HTMLDivElement
const item = (id: string) => ({ id, name: `Camiseta ${id}`, size: 'S', current_stock: 3, stock_loja: 1, stock_deposito: 2,
  sale_price: 10, is_active: true, alert_level: 'ok', created_at: '2026-10-08T10:00:00Z' } as InventoryItem)
async function flush() { for (let i = 0; i < 12; i++) { await Promise.resolve(); await nextTick() } }
async function mount() {
  root = document.createElement('div'); document.body.append(root)
  const pinia = createPinia(); setActivePinia(pinia)
  app = createApp(InventoryListView).use(pinia).use(createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } }))
  app.mount(root); await flush()
  return useInventoryStore()
}
function button(text: string) {
  const el = Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find(b => b.textContent?.trim() === text)
  if (!el) throw new Error(`Missing ${text}`)
  return el
}
beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear(); auth.userRole = 'ADMIN'
  vi.stubGlobal('IntersectionObserver', class { observe() {} disconnect() {} unobserve() {} })
  api.getGroups.mockResolvedValue([]); api.getAlertsSummary.mockResolvedValue(null); api.getSuppliers.mockResolvedValue([])
  api.getDistinctValues.mockResolvedValue({ brands: [], categories: [] })
  api.getItems.mockResolvedValue({ items: [item('a'), item('b')], page: 1, page_size: 2, total: 50000, total_pages: 25000 })
})
afterEach(() => { app?.unmount(); root?.remove(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

it('hides the floating selection toolbar while the list modal is open and keeps selection after closing', async () => {
  await mount()
  button('Selecionar').click(); await flush()
  root.querySelector<HTMLElement>('[data-item-id="a"]')!.click(); await flush()
  expect(root.querySelector('.sel-count')?.textContent).toContain('1')
  button('Imprimir lista').click(); await flush()
  // Vue waits for a transition frame before removing the toolbar node.
  await vi.waitFor(() => expect(root.querySelector('.selection-bar')).toBeNull())
  expect(root.querySelector('.count-modal-test span')?.textContent).toBe('a')
  button('Fechar lista').click(); await flush()
  expect(root.querySelector('.selection-bar')).not.toBeNull()
  expect(root.querySelector('[data-item-id="a"]')?.classList.contains('card-selected')).toBe(true)
  expect(root.querySelector('.sel-count')?.textContent).toContain('1')
  expect(api.getItems).toHaveBeenCalledOnce()
})

it('passes IDs still selected outside the current list and selects only loaded items, not the whole catalog', async () => {
  const store = await mount()
  button('Selecionar').click(); await flush()
  root.querySelector<HTMLElement>('[data-item-id="a"]')!.click(); await flush()
  const selectAll = Array.from(root.querySelectorAll<HTMLButtonElement>('.selection-bar button')).find(b => b.textContent?.includes('Sel. todos'))!
  selectAll.click(); await flush()
  expect(root.querySelector('.sel-count')?.textContent).toContain('2')
  store.items = [item('c')]; await flush()
  expect(root.querySelector('.sel-outside-view')?.textContent).toContain('2 fora da lista atual')
  button('Imprimir lista').click(); await flush()
  expect(root.querySelector('.count-modal-test span')?.textContent).toBe('a,b')
  expect(api.getItems).toHaveBeenCalledOnce()
})

it('does not expose the list print action to non-manager profiles', async () => {
  auth.userRole = 'VENDEDOR'; await mount()
  button('Selecionar').click(); await flush()
  root.querySelector<HTMLElement>('[data-item-id="a"]')!.click(); await flush()
  expect(root.querySelector('.selection-bar')?.textContent).not.toContain('Imprimir lista')
})
