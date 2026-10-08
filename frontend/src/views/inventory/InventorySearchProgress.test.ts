import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import InventoryListView from './InventoryListView.vue'
import { useInventoryStore } from '@/stores/inventory'
import type { InventoryItem } from '@/services/api'

const api = vi.hoisted(() => ({ getItems: vi.fn(), getGroups: vi.fn(), getAlertsSummary: vi.fn(), getSuppliers: vi.fn(), getDistinctValues: vi.fn() }))
vi.mock('@/services/api', () => ({ inventoryAPI: api, ocrAPI: {} }))
vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ isOwner: false }) }))
let app: App | undefined, root: HTMLDivElement, observe: (entries: { isIntersecting: boolean }[]) => void
const item = (id: string) => ({ id, name: `Camiseta ${id}`, size: 'S', current_stock: 1, stock_loja: 1, stock_deposito: 0,
  sale_price: 10, is_active: true, alert_level: 'ok', created_at: '2026-10-08T10:00:00Z' } as InventoryItem)
const page = (ids: string[], n = 1, total = 5) => ({ items: ids.map(item), page: n, page_size: 2, total, total_pages: Math.ceil(total / 2) })
function deferred() {
  let resolve!: (value: unknown) => void, reject!: (reason: unknown) => void
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
async function mount() {
  root = document.createElement('div'); document.body.append(root)
  const pinia = createPinia(); setActivePinia(pinia)
  const i18n = createI18n({ legacy: false, locale: 'pt', fallbackLocale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp(InventoryListView).use(pinia).use(i18n); app.mount(root)
  await nextTick()
  return { store: useInventoryStore(), i18n }
}
function button(text: string) {
  const el = Array.from(root.querySelectorAll('button')).find(b => b.textContent?.trim() === text)
  if (!el) throw new Error(`Missing button ${text}`)
  return el
}
const text = (selector: string) => root.querySelector(selector)?.textContent || ''
function search(value: string) {
  const input = root.querySelector<HTMLInputElement>('.search-input')!
  input.value = value; input.dispatchEvent(new Event('input', { bubbles: true }))
}
beforeEach(() => {
  localStorage.clear(); vi.resetAllMocks()
  vi.stubGlobal('IntersectionObserver', class {
    constructor(callback: typeof observe) { observe = callback }
    observe() {} disconnect() {} unobserve() {}
  })
  api.getGroups.mockResolvedValue([]); api.getAlertsSummary.mockResolvedValue(null); api.getSuppliers.mockResolvedValue([])
  api.getDistinctValues.mockResolvedValue({ brands: [], categories: [] }); api.getItems.mockResolvedValue(page(['a', 'b']))
})
afterEach(() => { app?.unmount(); root?.remove(); vi.useRealTimers(); vi.unstubAllGlobals() })

describe('Inventory search counts and mobile progress', () => {
  it('shows the full total beside Select, partial progress, then explicit end of results', async () => {
    const initial = deferred(); api.getItems.mockReturnValueOnce(initial.promise)
    await mount()
    expect(text('.selection-results')).toContain('Selecionar'); expect(text('.search-result-count')).toContain('Buscando...')
    expect(text('.mobile-search-progress')).toContain('Buscando...')
    initial.resolve(page(['a', 'b']))
    await vi.waitFor(() => expect(text('.search-result-count')).toContain('5 itens'))
    expect(text('.mobile-search-progress')).toContain('2 de 5 itens carregados')
    expect(text('.scroll-sentinel')).toContain('Role para ver mais')
    expect(api.getItems).toHaveBeenCalledTimes(1) // No background download of the whole catalog.
    const more = deferred(); api.getItems.mockReturnValueOnce(more.promise)
    button('Carregar mais').click(); await nextTick()
    expect(text('.mobile-search-progress')).toContain('Carregando mais itens...')
    expect(text('.search-result-count')).toContain('5 itens')
    more.resolve(page(['c', 'd'], 2))
    await vi.waitFor(() => expect(text('.loaded-result-count')).toContain('4 de 5'))
    api.getItems.mockResolvedValueOnce(page(['e'], 3)); button('Carregar mais').click()
    await vi.waitFor(() => expect(text('.results-complete')).toContain('Fim dos resultados'))
    expect(text('.loaded-result-count')).toContain('5 de 5'); expect(text('.mobile-search-progress')).toContain('Busca concluída')
  })
  it('does not prefetch all pages from a stale visible sentinel after appending results', async () => {
    await mount(); await vi.waitFor(() => expect(api.getDistinctValues).toHaveBeenCalled())
    const more = deferred(); api.getItems.mockReturnValueOnce(more.promise)
    observe([{ isIntersecting: true }])
    expect(api.getItems).toHaveBeenCalledTimes(2)
    const sentinel = root.querySelector<HTMLElement>('.scroll-sentinel')!
    vi.spyOn(sentinel, 'getBoundingClientRect').mockReturnValue({ top: 4000 } as DOMRect)
    more.resolve(page(['c', 'd'], 2, 8))
    await vi.waitFor(() => expect(text('.loaded-result-count')).toContain('4 de 8'))
    expect(api.getItems).toHaveBeenCalledTimes(2)
    expect(text('.mobile-search-progress')).toContain('Mais resultados abaixo')
  })
  it('keeps results on an append error, never loops retries, and offers a manual retry', async () => {
    await mount(); await vi.waitFor(() => expect(api.getDistinctValues).toHaveBeenCalled())
    api.getItems.mockRejectedValueOnce(new Error('offline')); observe([{ isIntersecting: true }])
    await vi.waitFor(() => expect(text('.load-more-error')).toContain('Os resultados já carregados foram mantidos'))
    expect(root.querySelectorAll('.item-card')).toHaveLength(2)
    expect(text('.mobile-search-progress')).toContain('Carregamento interrompido')
    observe([{ isIntersecting: true }]); await nextTick(); expect(api.getItems).toHaveBeenCalledTimes(2)
    api.getItems.mockResolvedValueOnce(page(['c'], 2, 3)); button('Tentar novamente').click()
    await vi.waitFor(() => expect(text('.results-complete')).toContain('Fim dos resultados'))
    expect(root.querySelectorAll('.item-card')).toHaveLength(3)
  })
  it('shows searching during debounce, ignores old replies and translates the completed total', async () => {
    const { i18n } = await mount(); await vi.waitFor(() => expect(api.getDistinctValues).toHaveBeenCalled())
    vi.useFakeTimers()
    const old = deferred(), fresh = deferred()
    api.getItems.mockReturnValueOnce(old.promise).mockReturnValueOnce(fresh.promise)
    search('calçados'); await nextTick()
    expect(text('.search-result-count')).toContain('Buscando...')
    await vi.advanceTimersByTimeAsync(300)
    search('camiseta S'); await nextTick(); await vi.advanceTimersByTimeAsync(300)
    fresh.resolve(page(['new'], 1, 1)); await vi.advanceTimersByTimeAsync(0)
    old.resolve(page(['old'], 1, 99)); await vi.advanceTimersByTimeAsync(0)
    expect(text('.search-result-count')).toContain('1 item'); expect(root.textContent).not.toContain('Camiseta old')
    i18n.global.locale.value = 'en'; await nextTick()
    expect(text('.mobile-search-progress')).toContain('Search complete')
    expect(text('.results-complete')).toContain('End of results')
  })
  it('waits for grades and counts matching variants rather than every contextual size', async () => {
    localStorage.setItem('inv_group_mode', 'true')
    api.getItems.mockResolvedValueOnce(page(['ungrouped'], 1, 1))
    const groups = deferred(); api.getGroups.mockReturnValueOnce(groups.promise)
    await mount(); await nextTick()
    expect(text('.search-result-count')).toContain('Buscando...')
    groups.resolve([{ group_key: 'Camisa', items: [item('S'), { ...item('M'), size: 'M' }], total_stock: 2, matching_count: 1 }])
    await vi.waitFor(() => expect(text('.search-result-count')).toContain('2 itens'))
    expect(text('.loaded-result-count')).toContain('2 de 2'); expect(root.querySelector('.group-card')).not.toBeNull()
  })
  it('does not report a completed or empty search when fetching grades fails', async () => {
    localStorage.setItem('inv_group_mode', 'true')
    api.getItems.mockResolvedValueOnce(page([], 1, 0)); api.getGroups.mockRejectedValueOnce(new Error('offline'))
    await mount(); await vi.waitFor(() => expect(root.querySelector('.list-load-error')).not.toBeNull())
    expect(text('.search-result-count')).toContain('Total não confirmado')
    expect(root.querySelector('.results-complete')).toBeNull(); expect(root.querySelector('.empty-state')).toBeNull()
    api.getItems.mockResolvedValueOnce(page([], 1, 0)); button('Tentar novamente').click()
    await vi.waitFor(() => expect(text('.search-result-count')).toContain('0 itens'))
    expect(text('.empty-state')).toContain('Nenhum item encontrado')
  })
})
