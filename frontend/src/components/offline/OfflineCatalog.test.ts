import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import OfflineCatalog from './OfflineCatalog.vue'
import { offlineCatalogState, type OfflineCatalogItem } from '@/services/offlineCatalog'

const mocks = vi.hoisted(() => ({ search: vi.fn(), facets: vi.fn(), photo: vi.fn(), scan: undefined as undefined | ((code: string) => void), locale: 'pt-BR' }))
vi.mock('@/services/offlineCatalog', async () => {
  const { reactive } = await import('vue')
  return { searchOfflineCatalog: mocks.search, getOfflineCatalogFacets: mocks.facets, loadOfflineThumbnail: mocks.photo,
    offlineCatalogState: reactive({ supported: true, loading: false, count: 1, syncedAt: Date.parse('2026-11-17T15:30:00Z') }) }
})
vi.mock('@/i18n/uiText', () => ({ uiLocale: () => mocks.locale }))
vi.mock('@/components/ui/ErpSelect.vue', async () => {
  const { defineComponent, h } = await import('vue')
  return { default: defineComponent({ props: ['modelValue', 'label'], emits: ['update:modelValue'], setup(props, { emit, slots }) {
    return () => h('select', { value: props.modelValue, 'aria-label': props.label, onChange: (event: Event) => emit('update:modelValue', (event.target as HTMLSelectElement).value) }, slots.default?.())
  } }) }
})
vi.mock('@/components/inventory/BarcodeScanner.vue', async () => {
  const { defineComponent, getCurrentInstance, h } = await import('vue')
  return { default: defineComponent({ emits: ['barcode-detected', 'close'], setup(_, { emit }) {
    mocks.scan = getCurrentInstance()!.vnode.props?.onBarcodeDetected as (code: string) => void
    return () => h('button', { 'data-testid': 'scanner-result', onClick: () => emit('barcode-detected', 'INV-ABC123') }, 'Synthetic scan')
  } }) }
})

let app: App | undefined, root: HTMLDivElement
const flush = async () => { for (let i = 0; i < 7; i++) { await Promise.resolve(); await nextTick() } }
const byLabel = (label: string) => root.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`)!
const button = (label: string) => Array.from(root.querySelectorAll('button')).find(value => value.textContent?.trim() === label)!
function row(changes: Partial<OfflineCatalogItem> = {}): OfflineCatalogItem {
  return { id: 'item-1', name: 'Camiseta azul', inventory_code: 'INV-ABC123', sku_internal: 'old-reference', barcode: '123456',
    brand: 'Boss', category: 'Camisetas', color: 'Azul', size: 'M', group_key: 'grade-1', location: 'A1', unit: 'un',
    description: 'Placa de metal na frente', sale_price: 25.5, sale_currency: 'USD', is_active: true, has_image: false,
    created_at: '2026-11-16T15:00:00Z', updated_at: '2026-11-17T15:00:00Z', snapshot_at: '2026-11-17T15:30:00Z',
    current_stock: 5, stock_loja: 2, stock_deposito: 3, reserved_loja: 1, reserved_deposito: 0,
    available_loja: 1, available_deposito: 3, available_stock: 4, stock_confirmed: true, min_stock: 1, max_stock: 10, ...changes }
}
function response(items = [row()], total = items.length) { return { items, total, syncedAt: offlineCatalogState.syncedAt, startedAt: offlineCatalogState.syncedAt } }
async function mount(props: Record<string, unknown> = {}) { app = createApp(OfflineCatalog, { userName: 'Lucas', ...props }); app.mount(root); await flush() }
async function search(value: string) {
  const input = root.querySelector<HTMLInputElement>('[data-testid="offline-query"]')!
  input.value = value; input.dispatchEvent(new Event('input', { bubbles: true })); await nextTick()
  await vi.advanceTimersByTimeAsync(181); await flush()
}
beforeEach(() => {
  root = document.createElement('div'); document.body.append(root)
  mocks.locale = 'pt-BR'; mocks.scan = undefined
  Object.assign(offlineCatalogState, { supported: true, loading: false, count: 1, syncedAt: Date.parse('2026-11-17T15:30:00Z') })
  mocks.search.mockResolvedValue(response())
  mocks.facets.mockResolvedValue({ brands: ['Boss'], categories: ['Camisetas'], colors: ['Azul'], sizes: ['M'] })
  mocks.photo.mockResolvedValue(null)
})
afterEach(() => { app?.unmount(); app = undefined; root.remove(); vi.useRealTimers(); vi.clearAllMocks() })

it('shows saved quantities by location, original currency and only consultation actions', async () => {
  const retry = vi.fn(), logout = vi.fn()
  await mount({ onRetry: retry, onLogout: logout })
  expect(root.querySelector('main')).toBeNull()
  expect(root.textContent).toContain('Podem ter mudado na loja')
  expect(root.textContent).toContain('17/11/2026')
  expect(root.textContent).toContain('Camiseta azul')
  expect(root.textContent).toContain('INV-ABC123')
  expect(root.querySelector('.offline-product__price')?.textContent).toContain('25,50')
  expect(root.querySelector('.offline-product__stock')?.textContent).toContain('2 L|3 D')
  expect(root.querySelector('.offline-product__availability')?.textContent).toContain('Disponível: 4Reservado: 1')
  button('Detalhes').click(); await flush()
  expect(root.textContent).toContain('Placa de metal na frente')
  expect(root.querySelector('table')?.textContent).toContain('Físico23Reservado10Disponível13')
  expect(Array.from(root.querySelectorAll('button')).map(value => value.textContent).join(' ')).not.toMatch(/Vender|Adicionar|Imprimir|Editar|Movimentar/)
  button('Conectar').click(); byLabel('Sair').click()
  expect(retry).toHaveBeenCalledOnce(); expect(logout).toHaveBeenCalledOnce()
})

it('keeps unknown balances and prices distinct from zero and marks confirmed negatives', async () => {
  mocks.search.mockResolvedValue(response([row({ id: 'unknown', stock_confirmed: false, stock_loja: 0, stock_deposito: null, sale_price: null }),
    row({ id: 'negative', stock_loja: -1, stock_deposito: 0, current_stock: -1, available_loja: -1, available_deposito: 0, available_stock: -1, reserved_loja: 0 })]))
  await mount()
  const unknown = root.querySelector('[data-product-id="unknown"]')!
  expect(unknown.textContent).toContain('Saldo não confirmado')
  expect(unknown.querySelector('.offline-product__stock')?.textContent).toContain('— L|— D')
  expect(unknown.querySelector('.offline-product__availability')?.textContent).toContain('Disponível: —Reservado: —')
  expect(unknown.querySelector('.offline-product__price')?.textContent).toBe('—')
  expect(root.querySelector('.negative-stock')?.textContent).toBe('-1 L')
})

it('debounces local search, paginates and resets the page for new text or filters', async () => {
  vi.useFakeTimers(); mocks.search.mockResolvedValue(response([row()], 120)); await mount()
  byLabel('Próxima página').click(); await flush()
  expect(mocks.search).toHaveBeenLastCalledWith('', expect.any(Object), { limit: 50, offset: 50 })
  expect(root.querySelector('.offline-catalog__pagination')?.textContent).toContain('2 / 3')
  await search('Placa')
  expect(mocks.search).toHaveBeenLastCalledWith('Placa', expect.any(Object), { limit: 50, offset: 0 })
  byLabel('Filtros').click(); await flush()
  const brand = root.querySelector<HTMLSelectElement>('select[aria-label="Marca"]')!
  brand.value = 'Boss'; brand.dispatchEvent(new Event('change')); await nextTick(); await vi.advanceTimersByTimeAsync(181)
  expect(mocks.search).toHaveBeenLastCalledWith('Placa', expect.objectContaining({ brand: 'Boss' }), { limit: 50, offset: 0 })
})

it('QR only runs a local search and clears filters that would hide the identified product', async () => {
  vi.useFakeTimers(); await mount()
  byLabel('Filtros').click(); await flush()
  const brand = root.querySelector<HTMLSelectElement>('select[aria-label="Marca"]')!
  brand.value = 'Boss'; brand.dispatchEvent(new Event('change')); await nextTick(); await vi.advanceTimersByTimeAsync(181)
  byLabel('Ler QR ou código de barras').click(); await flush()
  root.querySelector<HTMLButtonElement>('[data-testid="scanner-result"]')!.click(); await flush()
  expect(mocks.search).toHaveBeenLastCalledWith('INV-ABC123', expect.objectContaining({ brand: '' }), { limit: 50, offset: 0 })
  expect(root.querySelector('[data-testid="scanner-result"]')).toBeNull()
})

it('ignores a late scan callback and delayed local responses after logout/unmount', async () => {
  await mount(); byLabel('Ler QR ou código de barras').click(); await flush()
  const callback = mocks.scan!
  app!.unmount(); app = undefined
  const count = mocks.search.mock.calls.length
  callback('INV-LATE12'); await flush()
  expect(mocks.search).toHaveBeenCalledTimes(count)
})

it('a slower earlier search never replaces newer results', async () => {
  vi.useFakeTimers(); await mount()
  let resolveOld!: (value: ReturnType<typeof response>) => void
  mocks.search.mockImplementation((q: string) => q === 'old' ? new Promise(resolve => { resolveOld = resolve }) : Promise.resolve(response([row({ name: 'Resultado novo' })])))
  await search('old'); await search('new')
  resolveOld(response([row({ name: 'Resultado antigo' })])); await flush()
  expect(root.textContent).toContain('Resultado novo'); expect(root.textContent).not.toContain('Resultado antigo')
})

it('distinguishes a missing snapshot, no matches and a failed local read', async () => {
  offlineCatalogState.syncedAt = 0; offlineCatalogState.count = 0
  mocks.search.mockResolvedValue(response([])); await mount()
  expect(root.textContent).toContain('Nenhum catálogo salvo neste aparelho')
  offlineCatalogState.syncedAt = Date.parse('2026-11-17T15:30:00Z'); offlineCatalogState.count = 12; await flush()
  expect(root.textContent).toContain('Nenhum produto nesta busca')
  mocks.search.mockRejectedValueOnce(new Error('private internal storage error'))
  offlineCatalogState.count = 13; await flush()
  expect(root.textContent).toContain('Não foi possível ler a cópia local')
  expect(root.textContent).not.toContain('private internal storage error')
  mocks.search.mockResolvedValue(response()); button('Tentar novamente').click(); await flush()
  expect(root.textContent).toContain('Camiseta azul')
})

it('reloads products and complete facets when the snapshot becomes ready after mount', async () => {
  offlineCatalogState.syncedAt = 0; offlineCatalogState.count = 0; offlineCatalogState.loading = true
  mocks.search.mockResolvedValue(response([])); await mount()
  mocks.search.mockResolvedValue(response([row({ name: 'Produto recém-salvo' })]))
  offlineCatalogState.syncedAt = Date.parse('2026-11-17T15:30:00Z'); offlineCatalogState.count = 1; offlineCatalogState.loading = false
  await flush()
  expect(root.textContent).toContain('Produto recém-salvo')
  expect(mocks.facets).toHaveBeenCalledTimes(2)
})

it('uses stored thumbnail data only and never requests a remote or full-size photo', async () => {
  mocks.search.mockResolvedValue(response([row({ has_image: true }), row({ id: 'remote', has_image: true }), row({ id: 'missing', has_image: true })]))
  mocks.photo.mockImplementation((id: string) => Promise.resolve(id === 'item-1' ? 'data:image/jpeg;base64,/9j/AA==' : id === 'remote' ? 'https://example.com/private.jpg' : null))
  await mount()
  expect(mocks.photo).toHaveBeenCalledWith('item-1', '2026-11-17T15:00:00Z')
  expect(root.querySelectorAll('img')).toHaveLength(1)
  expect(root.querySelector('img')?.src).toMatch(/^data:image\/jpeg;base64,/)
  root.querySelector<HTMLButtonElement>('.offline-product__photo')!.click(); await flush()
  expect(root.querySelectorAll('img')).toHaveLength(2)
  expect(mocks.photo).toHaveBeenCalledTimes(3)
})

it('disables reconnection while pending and localizes interface without translating catalog data', async () => {
  mocks.locale = 'es-PY'; await mount({ loading: true })
  expect(button('Conectando…').disabled).toBe(true)
  expect(root.textContent).toContain('Consulta sin conexión')
  expect(root.textContent).toContain('Camiseta azul')
})
