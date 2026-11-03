import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import InventoryListView from './InventoryListView.vue'
import type { InventoryItem } from '@/services/api'

const api = vi.hoisted(() => ({ getItems: vi.fn(), getGroups: vi.fn(), getSuggestions: vi.fn(), getAlertsSummary: vi.fn(), getSuppliers: vi.fn(), getDistinctValues: vi.fn() }))
vi.mock('@/services/api', () => ({ inventoryAPI: { ...api, getItemPhotos: async () => ({ additional_images: [] }) }, ocrAPI: {} }))
vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ userRole: 'ADMIN', isOwner: false }) }))
vi.mock('@/components/inventory/ItemFormModal.vue', () => ({ default: {
  props: ['item'], emits: ['close'], template: '<section class="edit-test">{{ item.id }}<button @click="$emit(\'close\')">Fechar edição</button></section>',
} }))
vi.mock('@/components/inventory/MovementModal.vue', () => ({ default: {
  props: ['item'], emits: ['close'], template: '<section class="movement-test">{{ item.id }}<button @click="$emit(\'close\')">Fechar movimento</button></section>',
} }))
vi.mock('@/components/inventory/GradeMembershipModal.vue', () => ({ default: {
  props: ['groupKey'], emits: ['close'], template: '<section class="grade-test">{{ groupKey }}<button @click="$emit(\'close\')">Fechar grade</button></section>',
} }))

let app: App | undefined, root: HTMLDivElement
const photo = 'data:image/png;base64,aW1hZ2U='
const item = (id: string, overrides: Partial<InventoryItem> = {}) => ({ id, name: `Camiseta ${id}`, size: 'S', current_stock: 3, stock_loja: 1, stock_deposito: 2,
  sale_price: 10, is_active: true, alert_level: 'ok', created_at: '2026-10-08T10:00:00Z', ...overrides } as InventoryItem)
const a = () => item('a', { group_key: 'Grade A', image_data: photo, barcode: '123456789' })
const b = () => item('b', { group_key: 'Grade A', size: 'M', stock_loja: 0, stock_deposito: 3 })
const group = () => ({ group_key: 'Grade A', items: [a(), b()], total_stock: 6, matching_count: 1 })
async function flush() { for (let i = 0; i < 12; i++) { await Promise.resolve(); await nextTick() } }
async function mount() {
  root = document.createElement('div'); document.body.append(root)
  const pinia = createPinia(); setActivePinia(pinia)
  const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp(InventoryListView).use(pinia).use(i18n); app.mount(root); await flush()
  return i18n
}
function button(text: string) {
  const el = Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find(b => b.textContent?.trim() === text)
  if (!el) throw new Error(`Missing ${text}`)
  return el
}
function balances(selector: string) { return root.querySelector(selector)?.textContent?.trim().replace(/\s+/g, ' ') }
beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear()
  vi.stubGlobal('IntersectionObserver', class { observe() {} disconnect() {} unobserve() {} })
  vi.stubGlobal('matchMedia', () => ({ matches: true }))
  api.getGroups.mockResolvedValue([group()]); api.getSuggestions.mockResolvedValue([])
  api.getAlertsSummary.mockResolvedValue(null); api.getSuppliers.mockResolvedValue([])
  api.getDistinctValues.mockResolvedValue({ brands: [], categories: [] })
  api.getItems.mockResolvedValue({ items: [item('loose')], page: 1, page_size: 50, total: 1, total_pages: 1 })
})
afterEach(() => { app?.unmount(); root?.remove(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('Inventory grades and local balances across views', () => {
  it('keeps separate real balances at minimum zoom, including zero and an unknown local balance', async () => {
    localStorage.setItem('inv_view', 'grid'); localStorage.setItem('inv_mobile_grid_zoom', '0')
    api.getItems.mockResolvedValue({ items: [item('known', { current_stock: 99 }), item('zero', { stock_loja: 0 }), item('unknown', { current_stock: 9, stock_loja: null })], page: 1, page_size: 50, total: 3, total_pages: 1 })
    const i18n = await mount()
    expect(root.querySelector('.items-container')?.classList.contains('grid-zoom-0')).toBe(true)
    expect(balances('[data-item-id="known"] .stock-number')).toBe('1 L | 2 D')
    expect(balances('[data-item-id="zero"] .stock-number')).toBe('0 L | 2 D')
    expect(balances('[data-item-id="unknown"] .stock-number')).toBe('— L | 2 D')
    expect(root.querySelector('[data-item-id="unknown"] .stock-balances')?.getAttribute('aria-label')).toBe('Loja: Não informado · Depósito: 2')
    expect(root.querySelector('.dense-stock-total')).toBeNull()
    i18n.global.locale.value = 'en'; await nextTick()
    expect(balances('[data-item-id="known"] .stock-number')).toBe('1 S | 2 W')
    i18n.global.locale.value = 'es'; await nextTick()
    expect(balances('[data-item-id="known"] .stock-number')).toBe('1 T | 2 D')
  })

  it('keeps grades as cards in compact and square views, supports list and mobile zoom without reloading or dropping selection', async () => {
    localStorage.setItem('inv_group_mode', 'true'); localStorage.setItem('inv_view', 'grid')
    await mount()
    expect(root.querySelectorAll('.group-card')).toHaveLength(1)
    expect(balances('.group-stock-balances')).toBe('1 L | 5 D')
    expect(root.querySelector('.group-context-note')?.textContent).toBe('1 de 2 variações correspondem aos filtros')
    expect(root.querySelector('.search-result-count')?.textContent).toContain('2 itens')
    expect(root.querySelector('.size-chips')).toBeNull()
    button('Selecionar').click(); await flush()
    root.querySelector<HTMLButtonElement>('.group-select-btn')!.click(); await flush()
    expect(root.querySelector('.sel-count')?.textContent).toBe('Itens selecionados: 2')
    const requests = [api.getItems.mock.calls.length, api.getGroups.mock.calls.length]
    for (const [label, mode] of [['Lista', 'list'], ['Compacto', 'compact'], ['Quadrados', 'grid']]) {
      const trigger = button(label)
      vi.spyOn(trigger, 'getBoundingClientRect').mockReturnValue({ left: 80, bottom: 240, width: 34 } as DOMRect)
      trigger.click(); await flush()
      expect(root.querySelector('.items-container')?.classList.contains(`view-${mode}`)).toBe(true)
      expect(root.querySelector('.group-card.card-selected')).not.toBeNull()
      expect(root.querySelector('.group-total-stock')?.textContent).toContain('6')
      expect(root.querySelector('.size-chips, .group-exp-section, .group-barcode, .group-loc-badge, .group-manage-btn')).toBeNull()
      root.querySelector<HTMLButtonElement>('.expand-btn')!.click(); await flush()
      expect(root.querySelector('.expand-btn')?.getAttribute('aria-expanded')).toBe('true')
      expect(Array.from(root.querySelectorAll('.size-chip .stock-balances')).map(el => el.textContent?.trim().replace(/\s+/g, ' '))).toEqual(['1 L | 2 D', '0 L | 3 D'])
      expect(root.querySelectorAll('.group-exp-row')).toHaveLength(2)
      expect(root.querySelector('.group-barcode')?.textContent).toContain('123456789')
      expect(root.querySelector('.group-manage-btn')).not.toBeNull()
      root.querySelector<HTMLButtonElement>('.expand-btn')!.click(); await flush()
      expect(root.querySelector('.expand-btn')?.getAttribute('aria-expanded')).toBe('false')
      expect(root.querySelector('.group-card.card-selected')).not.toBeNull()
      expect(root.querySelector('.size-chips, .group-exp-section')).toBeNull()
    }
    const range = root.querySelector<HTMLInputElement>('[type="range"]')!
    range.value = '0'; range.dispatchEvent(new Event('input', { bubbles: true })); await flush()
    expect(root.querySelector('.items-container')?.classList.contains('grid-zoom-0')).toBe(true)
    expect(balances('.group-stock-balances')).toBe('1 L | 5 D')
    expect(root.querySelector('.sel-count')?.textContent).toBe('Itens selecionados: 2')
    expect([api.getItems.mock.calls.length, api.getGroups.mock.calls.length]).toEqual(requests)
  })

  it('retains known location totals when another location is unknown and never substitutes the total in a grade chip', async () => {
    localStorage.setItem('inv_group_mode', 'true')
    api.getGroups.mockResolvedValue([{ ...group(), items: [item('a', { group_key: 'Grade A', current_stock: null, stock_loja: null }), b()], total_stock: null }])
    await mount()
    expect(balances('.group-stock-balances')).toBe('— L | 5 D')
    expect(root.querySelector('.group-total-stock')?.textContent).toContain('—')
    root.querySelector<HTMLButtonElement>('.expand-btn')!.click(); await flush()
    expect(balances('.size-chip .stock-balances')).toBe('— L | 2 D')
    expect(root.querySelector<HTMLButtonElement>('[aria-label="Movimentar Camiseta a"]')?.disabled).toBe(true)
    expect(root.querySelector<HTMLButtonElement>('[aria-label="Movimentar Camiseta b"]')?.disabled).toBe(false)
  })

  it('keeps photo, grade management, per-variant editing and movements available without selecting the grade', async () => {
    localStorage.setItem('inv_group_mode', 'true'); localStorage.setItem('inv_view', 'grid'); localStorage.setItem('inv_mobile_grid_zoom', '0')
    await mount(); button('Selecionar').click(); await flush()
    root.querySelector<HTMLButtonElement>('.group-thumb-wrap')!.click(); await flush()
    expect(document.body.querySelector('.gallery-main')?.getAttribute('src')).toBe(photo)
    expect(root.querySelector('.group-card.card-selected')).toBeNull()
    document.body.querySelector<HTMLButtonElement>('[data-dialog-close]')!.click(); await flush()
    root.querySelector<HTMLButtonElement>('.expand-btn')!.click(); await flush()
    root.querySelector<HTMLButtonElement>('.group-manage-btn')!.click(); await flush()
    expect(root.querySelector('.grade-test')?.textContent).toContain('Grade A')
    button('Fechar grade').click(); await flush()
    root.querySelector<HTMLButtonElement>('.chip-label')!.click(); await flush()
    expect(root.querySelector('.edit-test')?.textContent).toContain('a')
    button('Fechar edição').click(); await flush()
    expect(root.querySelector('.expand-btn')?.getAttribute('aria-expanded')).toBe('true')
    root.querySelector<HTMLButtonElement>('.exp-move')!.click(); await flush()
    expect(root.querySelector('.movement-test')?.textContent).toContain('a')
    expect(root.querySelector('.group-card.card-selected')).toBeNull()
  })
})
