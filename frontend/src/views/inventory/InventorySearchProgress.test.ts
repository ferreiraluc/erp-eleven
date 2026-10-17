import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import InventoryListView from './InventoryListView.vue'
import { useInventoryStore } from '@/stores/inventory'
import type { InventoryItem } from '@/services/api'

const api = vi.hoisted(() => ({ getItems: vi.fn(), getGroups: vi.fn(), getAlertsSummary: vi.fn(), getSuppliers: vi.fn(), getDistinctValues: vi.fn() }))
vi.mock('@/services/api', () => ({ inventoryAPI: { ...api, getItemPhotos: async () => ({ additional_images: [] }) }, ocrAPI: {} }))
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
    expect(text('.search-result-count')).toContain('1 item'); expect(root.textContent).not.toContain('Older')
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

it('keeps default order until requested, resets pagination, and passes newest ordering to following pages', async () => {
  await mount(); await vi.waitFor(() => expect(api.getDistinctValues).toHaveBeenCalled())
  expect(api.getItems.mock.calls[0][0]).not.toHaveProperty('sort_by')
  const choose = async (value: string) => {
    const select = root.querySelector<HTMLSelectElement>('[aria-label="Ordenação dos produtos"]')!
    select.value = value; select.dispatchEvent(new Event('change', { bubbles: true })); await nextTick(); await nextTick()
  }
  await choose('created_at')
  expect(api.getItems).toHaveBeenLastCalledWith(expect.objectContaining({ sort_by: 'created_at', page: 1 }), expect.any(AbortSignal))
  api.getItems.mockResolvedValueOnce(page(['c', 'd'], 2)); button('Carregar mais').click(); await nextTick()
  expect(api.getItems).toHaveBeenLastCalledWith(expect.objectContaining({ sort_by: 'created_at', page: 2 }), expect.any(AbortSignal))
  await choose('')
  expect(api.getItems.mock.lastCall![0]).not.toHaveProperty('sort_by'); expect(api.getItems.mock.lastCall![0].page).toBe(1)
})

it('counts distinct selected grades and stock without counting contextual unselected sizes', async () => {
  api.getGroups.mockResolvedValue([{ group_key: 'Camisa', items: [{ ...item('a'), group_key: 'Camisa' }, { ...item('b'), group_key: 'Camisa' }], total_stock: 2 }])
  api.getItems.mockResolvedValue({ ...page(['a', 'b'], 1, 2), items: [{ ...item('a'), group_key: 'Camisa' }, { ...item('b'), group_key: 'Camisa' }] })
  await mount(); await vi.waitFor(() => expect(api.getDistinctValues).toHaveBeenCalled())
  button('Selecionar').click(); await nextTick(); root.querySelector<HTMLElement>('.item-card')!.click(); await nextTick()
  expect(text('.sel-stock-summary')).toBe('1 grades · 1 peças na seleção')
})

it('orders groups by their newest member alongside loose items only when newest is chosen', async () => {
  localStorage.setItem('inv_group_mode', 'true')
  api.getItems.mockResolvedValue({ ...page(['loose'], 1, 1), items: [{ ...item('loose'), created_at: '2026-10-10T12:00:00Z' }] })
  api.getGroups.mockResolvedValue([
    { group_key: 'Older', items: [{ ...item('old'), group_key: 'Older', created_at: '2026-10-01T10:00:00Z' }], total_stock: 1 },
    { group_key: 'Newer', items: [{ ...item('new'), group_key: 'Newer', created_at: '2026-10-12T10:00:00Z' }], total_stock: 1 },
  ])
  await mount(); await vi.waitFor(() => expect(api.getDistinctValues).toHaveBeenCalled())
  const names = () => Array.from(root.querySelectorAll('.items-container > .group-card, .items-container > .item-card')).map(el => el.textContent)
  expect(names()[0]).toContain('Older')
  const select = root.querySelector<HTMLSelectElement>('[aria-label="Ordenação dos produtos"]')!
  select.value = 'created_at'; select.dispatchEvent(new Event('change', { bubbles: true })); await nextTick(); await nextTick()
  expect(names()[0]).toContain('Newer'); expect(names()[1]).toContain('Camiseta loose'); expect(names()[2]).toContain('Older')
})

it('does not turn an unknown selected balance into zero', async () => {
  api.getItems.mockResolvedValue({ ...page(['a'], 1, 1), items: [{ ...item('a'), current_stock: null, stock_loja: null }] })
  await mount(); await vi.waitFor(() => expect(api.getDistinctValues).toHaveBeenCalled())
  button('Selecionar').click(); await nextTick(); root.querySelector<HTMLElement>('.item-card')!.click(); await nextTick()
  expect(text('.sel-stock-summary')).toContain('Não informado')
})

it('changes photo zoom without reloading results or losing selection, and remembers it across visits', async () => {
  vi.stubGlobal('matchMedia', () => ({ matches: true }))
  const openZoom = async () => {
    const trigger = button('Quadrados')
    vi.spyOn(trigger, 'getBoundingClientRect').mockReturnValue({ left: 80, bottom: 240, width: 34 } as DOMRect)
    trigger.click(); await nextTick(); await nextTick()
  }
  localStorage.setItem('inv_view', 'grid')
  await mount(); await vi.waitFor(() => expect(api.getDistinctValues).toHaveBeenCalled())
  button('Selecionar').click(); await nextTick(); root.querySelector<HTMLElement>('.item-card')!.click(); await nextTick()
  const requests = api.getItems.mock.calls.length
  expect(root.querySelector('[type="range"]')).toBeNull()
  await openZoom()
  const slider = root.querySelector<HTMLInputElement>('[type="range"]')!
  expect(slider.value).toBe('2')
  slider.value = '0'; slider.dispatchEvent(new Event('input', { bubbles: true })); await nextTick()
  expect(slider.getAttribute('aria-valuetext')).toBe('4 colunas')
  expect(root.querySelector('.item-card.card-selected')?.getAttribute('data-item-id')).toBe('a')
  expect(root.querySelectorAll('.item-card')).toHaveLength(2)
  expect(api.getItems).toHaveBeenCalledTimes(requests)
  expect(localStorage.getItem('inv_mobile_grid_zoom')).toBe('0')
  expect(root.querySelector<HTMLButtonElement>('[aria-label="Diminuir produtos"]')!.disabled).toBe(true)
  root.querySelector<HTMLButtonElement>('[aria-label="Aumentar produtos"]')!.click(); await nextTick()
  expect(slider.getAttribute('aria-valuetext')).toBe('3 colunas')
  app!.unmount(); root.remove()
  await mount(); await nextTick()
  await openZoom()
  expect(root.querySelector<HTMLInputElement>('[type="range"]')!.value).toBe('1')
})

it('opens the matching photo from the compact list thumbnail without selecting the product', async () => {
  localStorage.setItem('inv_view', 'list')
  const photo = 'data:image/png;base64,aW1hZ2U='
  api.getItems.mockResolvedValue({ ...page(['a', 'b']), items: [{ ...item('a'), image_data: photo }, item('b')] })
  await mount(); await vi.waitFor(() => expect(api.getDistinctValues).toHaveBeenCalled())
  button('Selecionar').click(); await nextTick()
  const thumbs = root.querySelectorAll<HTMLButtonElement>('.list-thumbnail')
  expect(thumbs[1].disabled).toBe(true)
  thumbs[0].click(); await nextTick()
  expect(root.querySelector('.card-selected')).toBeNull()
  expect(root.querySelector('.gallery-main')?.getAttribute('src')).toBe(photo)
})
