import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import InventoryListView from './InventoryListView.vue'
import { useInventoryStore } from '@/stores/inventory'
import type { InventoryItem } from '@/services/api'

const api = vi.hoisted(() => ({ getItems: vi.fn(), getGroups: vi.fn(), getSuggestions: vi.fn(), getAlertsSummary: vi.fn(), getSuppliers: vi.fn(), getDistinctValues: vi.fn() }))
let auth = reactive({ userRole: 'ADMIN', isOwner: false, user: { id: 'user-a' } })
vi.mock('@/services/api', () => ({ inventoryAPI: { ...api, getItemPhotos: async () => ({ additional_images: [] }) }, ocrAPI: {} }))
vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))
vi.mock('@/components/inventory/GradeAiModal.vue', () => ({ default: {
  props: ['itemIds'], emits: ['close', 'applied'],
  template: '<section role="dialog" class="grade-ai-test"><span>{{ itemIds.join(",") }}</span><button @click="$emit(\'close\')">Fechar IA</button><button @click="$emit(\'applied\', \'Boss\', itemIds.length)">Concluir vínculos teste</button></section>',
} }))

let app: App | undefined, root: HTMLDivElement
const item = (id: string) => ({ id, name: `Camisa ${id}`, size: 'S', current_stock: 3, stock_loja: 1, stock_deposito: 2,
  sale_price: 10, is_active: true, alert_level: 'ok', created_at: '2026-10-08T10:00:00Z' } as InventoryItem)
async function flush() { for (let i = 0; i < 10; i++) { await Promise.resolve(); await nextTick() } }
async function mount() {
  root = document.createElement('div'); document.body.append(root)
  const pinia = createPinia(); setActivePinia(pinia)
  const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp(InventoryListView).use(pinia).use(i18n); app.mount(root); await flush()
  return { store: useInventoryStore(), i18n }
}
function button(text: string) {
  const el = Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find(b => b.textContent?.trim() === text)
  if (!el) throw new Error(`Missing ${text}`)
  return el
}
async function selectTwo() {
  button('Selecionar').click(); await flush()
  for (const id of ['a', 'b']) root.querySelector<HTMLElement>(`[data-item-id="${id}"]`)!.click()
  await flush()
}
beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear(); auth = reactive({ userRole: 'ADMIN', isOwner: false, user: { id: 'user-a' } })
  vi.stubGlobal('IntersectionObserver', class { observe() {} disconnect() {} unobserve() {} })
  api.getGroups.mockResolvedValue([]); api.getSuggestions.mockResolvedValue([]); api.getAlertsSummary.mockResolvedValue(null); api.getSuppliers.mockResolvedValue([])
  api.getDistinctValues.mockResolvedValue({ brands: [], categories: [] })
  api.getItems.mockResolvedValue({ items: [item('a'), item('b')], page: 1, page_size: 50, total: 2, total_pages: 1 })
})
afterEach(() => { app?.unmount(); app = undefined; root?.remove(); vi.unstubAllGlobals() })

describe('Inventory AI entry and selection lifecycle', () => {
  it.each(['ADMIN', 'GERENTE'])('opens the selected IDs for %s, hides the floating bar and preserves selection when closing', async role => {
    auth.userRole = role; await mount()
    expect(root.querySelector('.grade-ai-test')).toBeNull()
    await selectTwo(); button('Grades com IA').click(); await flush()
    await vi.waitFor(() => expect(root.querySelector('.selection-bar')).toBeNull())
    expect(root.querySelector('.grade-ai-test span')?.textContent).toBe('a,b')
    expect(api.getItems).toHaveBeenCalledOnce()
    button('Fechar IA').click(); await flush()
    expect(root.querySelector('.grade-ai-test')).toBeNull()
    expect(root.querySelectorAll('.item-card.card-selected')).toHaveLength(2)
    expect(root.querySelector('.sel-count')?.textContent).toBe('Itens selecionados: 2')
  })

  it('passes selected IDs outside the current list without silently dropping them', async () => {
    const { store } = await mount(); await selectTwo()
    store.items = [item('c')]; await flush()
    expect(root.querySelector('.sel-outside-view')?.textContent).toContain('2 fora da lista atual')
    button('Grades com IA').click(); await flush()
    expect(root.querySelector('.grade-ai-test span')?.textContent).toBe('a,b')
    expect(api.getItems).toHaveBeenCalledOnce()
  })

  it('refreshes confirmed membership data and closes the modal while keeping selected products', async () => {
    await mount(); await selectTwo(); button('Grades com IA').click(); await flush()
    const calls = api.getGroups.mock.calls.length
    button('Concluir vínculos teste').click(); await flush()
    expect(root.querySelector('.grade-ai-test')).toBeNull()
    expect(api.getItems).toHaveBeenCalledTimes(2)
    expect(api.getGroups).toHaveBeenCalledTimes(calls + 1)
    expect(root.querySelectorAll('.item-card.card-selected')).toHaveLength(2)
  })

  it('does not expose the action to a seller and closes it if management permission is removed', async () => {
    await mount(); await selectTwo(); button('Grades com IA').click(); await flush()
    await vi.waitFor(() => expect(root.querySelector('.selection-bar')).toBeNull())
    expect(root.querySelector('.grade-ai-test')).not.toBeNull()
    auth.userRole = 'VENDEDOR'; await flush()
    expect(root.querySelector('.grade-ai-test')).toBeNull()
    expect(root.textContent).not.toContain('Grades com IA')
    expect(root.querySelector('.selection-bar')).not.toBeNull()
  })

  it.each([['es', 'Variantes con IA'], ['en', 'AI product groups']] as const)('translates the selection entry in %s', async (locale, label) => {
    const { i18n } = await mount(); await selectTwo()
    i18n.global.locale.value = locale; await flush()
    button(label).click(); await flush()
    expect(root.querySelector('.grade-ai-test span')?.textContent).toBe('a,b')
  })
})
