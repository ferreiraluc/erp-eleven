import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, reactive, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import InventoryDiagnosticsPanel from './InventoryDiagnosticsPanel.vue'
import { diagnosticsMessages } from './diagnosticsMessages'
import type { InventoryDiagnostics } from '@/services/inventoryDiagnostics'

const api = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/services/inventoryDiagnostics', () => ({ inventoryDiagnosticsAPI: api }))
const fixture = (): InventoryDiagnostics => ({ checked_at: '2026-10-01T10:15:00-03:00', total_active_items: 140, affected_items: 31,
  counts: { stock_mismatch: 20, negative_stock: 2, missing_stock: 3, duplicate_barcode: 12, duplicate_barcode_groups: 4 },
  total_items: 31, page: 1, page_size: 25, items: [{ id: 'item-1', name: 'Loja', sku_internal: 'A-1', barcode: ' ab 123 ',
    normalized_barcode: 'AB123', brand: 'Eleven', size: 'M', color: null, current_stock: 5, stock_loja: 0, stock_deposito: 3,
    expected_stock: 3, delta: 2, issues: ['stock_mismatch', 'duplicate_barcode'], duplicate_count: 4 }] })
function deferred<T>() { let resolve!: (value: T) => void, reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
let app: App | undefined, container: HTMLDivElement
async function mount(extra: Record<string, unknown> = {}) {
  container = document.createElement('div'); document.body.append(container)
  const props = reactive({ revision: 0, ...extra })
  const i18n = createI18n({ legacy: false, locale: 'pt', fallbackLocale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp(defineComponent({ setup: () => () => h(InventoryDiagnosticsPanel, props) })).use(i18n)
  app.mount(container); await nextTick(); return { i18n, props }
}
async function ready() {
  await nextTick() // Flush the synchronous loading state before inspecting the old DOM.
  await vi.waitFor(() => expect(container.querySelector('tbody')).not.toBeNull())
}
function button(text: string) {
  const found = Array.from(container.querySelectorAll('button')).find(b => b.textContent?.trim() === text)
  if (!found) throw new Error(`Button missing: ${text}`)
  return found
}
async function filter(value: string) {
  const select = container.querySelector('select') as HTMLSelectElement
  select.value = value; select.dispatchEvent(new Event('change', { bubbles: true })); await nextTick()
}
beforeEach(() => api.get.mockReset().mockResolvedValue(fixture()))
afterEach(async () => { app?.unmount(); app = undefined; container?.remove(); await nextTick(); vi.resetAllMocks() })

describe('Inventory diagnostics', () => {
  it('shows global counts, review warnings and missing balances without writing or translating item data', async () => {
    const data = fixture(); data.items.push({ ...data.items[0], id: 'item-2', current_stock: null, stock_loja: -1,
      stock_deposito: null, expected_stock: null, delta: null, issues: ['missing_stock', 'negative_stock'], duplicate_count: 0 })
    api.get.mockResolvedValue(data)
    const open = vi.fn(), { i18n } = await mount({ 'onOpen-item': open }); await ready()
    expect(api.get).toHaveBeenCalledWith({ issue: 'all', q: '', page: 1, page_size: 25 }, expect.any(AbortSignal))
    expect(container.querySelector('.diagnostics-summary')?.textContent).toContain('140')
    expect(container.querySelector('.diagnostics-summary')?.textContent).toContain('31')
    const first = container.querySelector('[data-item-id="item-1"]')!
    expect(Array.from(first.querySelectorAll('.stock-value')).map(c => c.textContent)).toEqual(['5', '0', '3', '3', '+2'])
    const second = container.querySelector('[data-item-id="item-2"]')!
    expect(Array.from(second.querySelectorAll('.stock-value')).map(c => c.textContent)).toEqual(['—', '-1', '—', '—', '—'])
    expect(container.textContent).toContain('Não há fusão de cadastros')
    i18n.global.locale.value = 'es'; await nextTick(); expect(container.textContent).toContain('Revisión de stock')
    i18n.global.locale.value = 'en'; await nextTick(); expect(container.textContent).toContain('Shared barcode')
    expect(first.querySelector('.diagnostic-product strong')?.textContent).toBe('Loja')
    button('Open product').click(); expect(open).toHaveBeenCalledWith('item-1')
    expect(api.get).toHaveBeenCalledTimes(1)
  })

  it('applies search and issue filters on page one, caps the query and resets filters', async () => {
    await mount(); await ready()
    const input = container.querySelector('input') as HTMLInputElement
    input.value = ' ' + 'A'.repeat(170) + ' '; input.dispatchEvent(new Event('input', { bubbles: true }))
    await filter('duplicate_barcode')
    expect(api.get).toHaveBeenLastCalledWith({ issue: 'duplicate_barcode', q: 'A'.repeat(150), page: 1, page_size: 25 }, expect.any(AbortSignal))
    await ready()
    button('Limpar filtros').click(); await nextTick()
    expect(api.get).toHaveBeenLastCalledWith({ issue: 'all', q: '', page: 1, page_size: 25 }, expect.any(AbortSignal))
  })

  it('paginates and returns to a valid page after a correction removes the last page', async () => {
    await mount(); await ready()
    api.get.mockResolvedValueOnce({ ...fixture(), page: 2 })
    button('Próxima').click(); await ready()
    expect(api.get).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 }), expect.any(AbortSignal))
    expect(container.textContent).toContain('Página 2 de 2')
    expect(button('Próxima').disabled).toBe(true)
    api.get.mockResolvedValueOnce({ ...fixture(), page: 2, total_items: 1, items: [] }).mockResolvedValueOnce({ ...fixture(), total_items: 1 })
    button('Conferir novamente').click(); await ready()
    expect(api.get).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1 }), expect.any(AbortSignal))
    expect(container.textContent).toContain('Página 1 de 1')
  })

  it('cancels an old request and ignores its late result after filters change', async () => {
    const first = deferred<InventoryDiagnostics>(); api.get.mockReturnValueOnce(first.promise)
    await mount()
    const signal = api.get.mock.calls[0][1] as AbortSignal
    api.get.mockResolvedValueOnce({ ...fixture(), total_items: 1, items: [{ ...fixture().items[0], name: 'New query' }] })
    await filter('negative_stock'); await ready()
    expect(signal.aborted).toBe(true)
    first.resolve({ ...fixture(), items: [{ ...fixture().items[0], name: 'Old query' }] }); await nextTick()
    expect(container.textContent).toContain('New query'); expect(container.textContent).not.toContain('Old query')
  })

  it('shows recoverable failures, discards old rows and handles a late rejection without hiding newer data', async () => {
    await mount(); await ready()
    api.get.mockRejectedValueOnce(new Error('network'))
    button('Conferir novamente').click()
    await vi.waitFor(() => expect(container.querySelector('[role="alert"]')?.textContent).toContain('Não foi possível'))
    expect(container.querySelector('tbody')).toBeNull()
    const old = deferred<InventoryDiagnostics>(); api.get.mockReturnValueOnce(old.promise)
    button('Tentar novamente').click(); await nextTick()
    api.get.mockResolvedValueOnce(fixture()); await filter('stock_mismatch'); await ready()
    old.reject(new Error('old failure')); await nextTick()
    expect(container.querySelector('[role="alert"]')).toBeNull()
    expect(container.querySelector('tbody')).not.toBeNull()
  })

  it('refreshes after manual changes and aborts its request when closed', async () => {
    const { props } = await mount(); await ready()
    const pending = deferred<InventoryDiagnostics>(); api.get.mockReturnValueOnce(pending.promise)
    props.revision++; await nextTick()
    expect(api.get).toHaveBeenCalledTimes(2)
    const signal = api.get.mock.calls[1][1] as AbortSignal
    app!.unmount(); app = undefined
    expect(signal.aborted).toBe(true)
    pending.resolve(fixture()); await nextTick()
    expect(api.get).toHaveBeenCalledTimes(2)
  })

  it('distinguishes empty filters from no global alerts and preserves localized catalog parameters', async () => {
    api.get.mockResolvedValue({ ...fixture(), items: [], total_items: 0 })
    const { props } = await mount()
    await vi.waitFor(() => expect(container.textContent).toContain('Nenhum item com alerta nesta consulta.'))
    api.get.mockResolvedValue({ ...fixture(), items: [], total_items: 0, affected_items: 0 }); props.revision++; await nextTick()
    await vi.waitFor(() => expect(container.textContent).toContain('Nenhum alerta encontrado nos itens ativos.'))
    const tokens = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort()
    for (const language of ['es', 'en'] as const) {
      expect(Object.keys(diagnosticsMessages[language])).toEqual(Object.keys(diagnosticsMessages.pt))
      for (const key of Object.keys(diagnosticsMessages.pt) as Array<keyof typeof diagnosticsMessages.pt>) {
        expect(tokens(diagnosticsMessages[language][key]), `${language}.${key}`).toEqual(tokens(diagnosticsMessages.pt[key]))
      }
    }
  })
})
