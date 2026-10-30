import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import { createRouter, createMemoryHistory } from 'vue-router'
import InventoryReplenishmentView from './InventoryReplenishmentView.vue'
import {
  canReplenish,
  replenishmentRequest,
  restoreReplenishmentRequest,
  type ReplenishmentProduct,
} from '@/services/inventoryReplenishment'
import { standardLabelLayout } from '@/test/productLabelDesign'
import { chooseDropdown } from '@/test/dropdown'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  confirm: vi.fn(),
  device: vi.fn(),
  layouts: vi.fn(),
  preview: vi.fn(),
  batch: vi.fn(),
  auth: { user: { id: 'owner' }, userRole: 'ADMIN', isOwner: true },
}))
vi.mock('@/services/inventoryReplenishment', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/inventoryReplenishment')>()),
  inventoryReplenishment: { list: mocks.list, confirm: mocks.confirm },
}))
vi.mock('@/services/productLabels', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/productLabels')>()),
  productLabels: {
    device: mocks.device,
    layouts: mocks.layouts,
    preview: mocks.preview,
    batch: mocks.batch,
  },
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))
vi.mock('@/components/inventory/ProductThumbnail.vue', () => ({
  default: { props: ['item', 'alt'], template: '<img :alt="alt" />' },
}))

const product: ReplenishmentProduct = {
  id: 'p1',
  name: 'Camiseta branca S',
  inventory_code: 'INV-A7K4P2',
  size: 'S',
  color: 'Branco',
  group_key: 'Camiseta',
  stock_loja: 0,
  stock_deposito: 4,
  current_stock: 4,
  sale_price: '100.00',
  sale_currency: 'USD',
  brand: 'Eleven',
  location: 'Prateleira 2',
  has_image: true,
  updated_at: '2026-10-30T10:00:00Z',
  blocked_reason: null,
  last_store_exit_at: '2026-10-30T10:25:00-03:00',
  has_store_history: true,
}
const other: ReplenishmentProduct = {
  ...product,
  id: 'p2',
  name: 'Camiseta azul M',
  inventory_code: 'INV-B7K4P2',
  size: 'M',
  color: 'Azul',
  stock_deposito: 2,
  current_stock: 2,
}
const blocked: ReplenishmentProduct = {
  ...product,
  id: 'p3',
  name: 'Produto para conferir',
  stock_loja: null,
  blocked_reason: 'Saldo não informado. Confira o estoque.',
}
const batch = {
  id: 'batch1',
  request_key: 'test-key',
  total: 1,
  replenished_items: 1,
  created_at: '2026-10-30T10:00:00Z',
  movements: [
    { id: 'move1', item_id: 'p1', quantity: 1, stock_loja: 1, stock_deposito: 3, current_stock: 4 },
  ],
  jobs: [
    {
      id: 'j1',
      name: product.name,
      code: product.inventory_code,
      color: product.color,
      size: product.size,
      copies: 1,
      status: 'pending',
      diagnostic_message: null,
    },
  ],
}
let app: App | undefined, root: HTMLDivElement, router: ReturnType<typeof createRouter>
async function flush() {
  for (let i = 0; i < 12; i++) {
    await Promise.resolve()
    await nextTick()
  }
}
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => {
    resolve = yes
    reject = no
  })
  return { promise, resolve, reject }
}
function buttons(text: string) {
  return Array.from(document.querySelectorAll<HTMLButtonElement>('button')).filter(
    (button) => button.textContent?.trim() === text,
  )
}
async function click(text: string, index = 0) {
  const button = buttons(text)[index]
  expect(button, text).toBeTruthy()
  button.click()
  await flush()
}
async function check(selector: string) {
  const input = document.querySelector<HTMLInputElement>(selector)!
  expect(input).toBeTruthy()
  input.checked = true
  input.dispatchEvent(new Event('change', { bubbles: true }))
  await flush()
}
async function quantity(value: string, index = 0) {
  const input = root.querySelectorAll<HTMLInputElement>('.product-actions input')[index]
  input.value = value
  input.dispatchEvent(new Event('input', { bubbles: true }))
  await flush()
}
async function mount(locale = 'pt') {
  root = document.createElement('div')
  document.body.append(root)
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/inventory', component: { template: '<div />' } },
      { path: '/inventory/labels', component: { template: '<div />' } },
    ],
  })
  app = createApp(InventoryReplenishmentView)
  app.use(createI18n({ legacy: false, locale, messages: { pt: {}, es: {}, en: {} } }))
  app.config.globalProperties.$router = router
  app.mount(root)
  await flush()
}
function unmount() {
  app?.unmount()
  app = undefined
  root?.remove()
}
beforeEach(() => {
  vi.resetAllMocks()
  sessionStorage.clear()
  localStorage.clear()
  mocks.auth = reactive({ user: { id: 'owner' }, userRole: 'ADMIN', isOwner: true })
  vi.stubGlobal('URL', { createObjectURL: vi.fn(() => 'blob:preview'), revokeObjectURL: vi.fn() })
  mocks.list.mockResolvedValue({
    items: [product, other, blocked],
    total: 3,
    page: 1,
    page_size: 40,
  })
  mocks.device.mockResolvedValue({
    device: { id: 'zebra', name: 'Zebra ZD220', last_seen_at: null },
  })
  mocks.layouts.mockResolvedValue([standardLabelLayout()])
  mocks.preview.mockResolvedValue(new Blob(['preview'], { type: 'image/png' }))
  mocks.confirm.mockImplementation((body) =>
    Promise.resolve({ ...batch, request_key: body.request_key }),
  )
  mocks.batch.mockResolvedValue(batch)
})
afterEach(() => {
  unmount()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

it('validates identity, coherent stock, quantity limits and recoverable frozen requests', () => {
  expect(canReplenish(product)).toBe(true)
  for (const invalid of [
    blocked,
    { ...product, stock_loja: 1 },
    { ...product, current_stock: 8 },
    { ...product, stock_deposito: 0 },
    { ...product, inventory_code: null },
  ])
    expect(canReplenish(invalid)).toBe(false)
  const body = replenishmentRequest([{ ...product, copies: 3 }], 'saved-key')
  expect(body.items[0]).toMatchObject({
    copies: 3,
    expected_stock_loja: 0,
    expected_stock_deposito: 4,
    expected_current_stock: 4,
    sale_price: '100.00',
    sale_currency: 'USD',
  })
  expect(restoreReplenishmentRequest(JSON.stringify(body))).toEqual(body)
  for (const copies of [0, 1.5, 5, Number.NaN])
    expect(() => replenishmentRequest([{ ...product, copies }], 'key')).toThrow()
  expect(() =>
    replenishmentRequest(
      [
        { ...product, copies: 1 },
        { ...product, copies: 1 },
      ],
      'key',
    ),
  ).toThrow()
  expect(() =>
    replenishmentRequest(
      Array.from({ length: 101 }, (_, i) => ({ ...product, id: `p${i}`, copies: 1 })),
      'key',
    ),
  ).toThrow()
  expect(() =>
    restoreReplenishmentRequest(
      JSON.stringify({ ...body, items: [{ ...body.items[0], sale_price: undefined }] }),
    ),
  ).toThrow()
  expect(() =>
    restoreReplenishmentRequest(
      JSON.stringify({ ...body, items: [{ ...body.items[0], expected_stock_loja: 2 }] }),
    ),
  ).toThrow()
})

it('shows known quantities, lazy thumbnails and blocks incoherent stock without making it zero', async () => {
  await mount()
  expect(root.textContent).toContain('3 produtos para conferir')
  expect(root.querySelectorAll('.product-photo')).toHaveLength(3)
  expect(root.querySelector('.blocked')?.textContent).toContain('Loja: —')
  expect(root.querySelector('.blocked')?.textContent).toContain(blocked.blocked_reason)
  expect(root.querySelector<HTMLInputElement>('.blocked .product-check')?.disabled).toBe(true)
  expect(root.querySelector('.blocked .product-actions')).toBeNull()
  const navigate = vi.spyOn(router, 'push')
  await click('Conferir estoque')
  expect(navigate).toHaveBeenCalledWith({ path: '/inventory', query: { item_id: 'p3' } })
  expect(mocks.confirm).not.toHaveBeenCalled()
})

it('shows the three store-history states while keeping the order supplied by the server', async () => {
  const withoutHistory = { ...blocked, last_store_exit_at: null, has_store_history: false }
  const undatedHistory = { ...other, last_store_exit_at: null, has_store_history: true }
  // Keep deliberately mixed order: ordering and pagination belong to the API.
  mocks.list.mockResolvedValue({
    items: [withoutHistory, product, undatedHistory],
    total: 3,
    page: 1,
    page_size: 40,
  })
  await mount()
  const rows = Array.from(root.querySelectorAll('.product-row'))
  expect(rows.map((row) => row.querySelector('.product-identity>strong')?.textContent)).toEqual([
    withoutHistory.name,
    product.name,
    undatedHistory.name,
  ])
  expect(rows[0].querySelector('.store-history')?.textContent).toBe('Sem histórico na loja')
  expect(rows[1].querySelector('.store-history')?.textContent).toContain('Última baixa na loja:')
  expect(rows[2].querySelector('.store-history')?.textContent).toBe('Já esteve na loja')
  expect(root.querySelector('.intro')?.textContent).toContain(
    'As últimas baixas na loja aparecem primeiro',
  )
  expect(mocks.confirm).not.toHaveBeenCalled()
})

it.each([
  ['pt', 'pt-BR', 'Última baixa na loja:'],
  ['es', 'es-PY', 'Última salida de la tienda:'],
  ['en', 'en-US', 'Last store stock exit:'],
])(
  'formats the last store exit in %s using its timezone-aware timestamp',
  async (locale, dateLocale, label) => {
    await mount(locale)
    const date = new Intl.DateTimeFormat(dateLocale, {
      dateStyle: 'short',
      timeStyle: 'short',
    }).format(new Date(product.last_store_exit_at!))
    expect(root.querySelector('.store-history')?.textContent).toBe(`${label} ${date}`)
  },
)

it('requires real preview and explicit confirmation before one atomic transfer plus labels', async () => {
  await mount()
  await quantity('3')
  await click('Reposto')
  expect(mocks.confirm).not.toHaveBeenCalled()
  expect(mocks.preview).toHaveBeenCalledWith('p1', undefined)
  expect(document.querySelector('.review-summary')?.textContent).toContain(
    '1 produtos · 3 unidades · 3 etiquetas',
  )
  expect(buttons('Confirmar reposição e imprimir')[0].disabled).toBe(true)
  expect(document.querySelector('.selection-footer')).toBeNull()
  await check('.confirmation-line input')
  const waiting = deferred<typeof batch>()
  mocks.confirm.mockReturnValueOnce(waiting.promise)
  const confirm = buttons('Confirmar reposição e imprimir')[0]
  confirm.click()
  confirm.click()
  await flush()
  expect(mocks.confirm).toHaveBeenCalledTimes(1)
  const body = mocks.confirm.mock.calls[0][0]
  expect(body.items).toEqual([
    expect.objectContaining({
      item_id: 'p1',
      copies: 3,
      expected_stock_loja: 0,
      expected_stock_deposito: 4,
      expected_current_stock: 4,
    }),
  ])
  expect(JSON.parse(sessionStorage.getItem('eleven-replenishment-confirmation:owner')!)).toEqual(
    body,
  )
  mocks.list.mockResolvedValueOnce({ items: [other, blocked], total: 2, page: 1, page_size: 40 })
  waiting.resolve({ ...batch, request_key: body.request_key })
  await flush()
  expect(root.textContent).toContain('Reposição registrada; etiquetas na fila.')
  expect(root.querySelectorAll('.product-row')).toHaveLength(2)
  expect(document.querySelector('.replenishment-dialog')).toBeNull()
  expect(document.body.style.overflow).not.toBe('hidden')
  expect(sessionStorage.getItem('eleven-replenishment-confirmation:owner')).toBeNull()
})

it('freezes the original request after timeout and recovers it after reload without a new preview or key', async () => {
  await mount()
  await quantity('2')
  await click('Reposto')
  await check('.confirmation-line input')
  mocks.confirm.mockRejectedValueOnce(new Error('timeout'))
  await click('Confirmar reposição e imprimir')
  const original = JSON.parse(JSON.stringify(mocks.confirm.mock.calls[0][0]))
  expect(buttons('Recuperar confirmação')).toHaveLength(2)
  await click('Cancelar')
  expect(buttons('Reposto')[0].disabled).toBe(true)
  unmount()
  mocks.preview.mockClear()
  mocks.device.mockRejectedValueOnce(new Error('offline'))
  await mount()
  expect(mocks.preview).not.toHaveBeenCalled()
  expect(document.querySelector('.replenishment-dialog')).not.toBeNull()
  await click('Recuperar confirmação', 1)
  expect(mocks.confirm).toHaveBeenCalledTimes(2)
  expect(mocks.confirm.mock.calls[1][0]).toEqual(original)
  expect(root.textContent).toContain('Reposição registrada; etiquetas na fila.')
})

it('does not send if session storage cannot preserve the request first', async () => {
  await mount()
  await click('Reposto')
  await check('.confirmation-line input')
  vi.spyOn(sessionStorage, 'setItem').mockImplementation(() => {
    throw new Error('quota')
  })
  await click('Confirmar reposição e imprimir')
  expect(mocks.confirm).not.toHaveBeenCalled()
  expect(document.body.textContent).toContain('Nenhuma reposição foi enviada')
})

it('keeps a successful result after list refresh fails and retrieves its queue after reload', async () => {
  await mount()
  await click('Reposto')
  await check('.confirmation-line input')
  mocks.list.mockRejectedValueOnce(new Error('offline'))
  await click('Confirmar reposição e imprimir')
  expect(root.textContent).toContain('Reposição registrada; etiquetas na fila.')
  expect(root.textContent).toContain('Não foi possível confirmar a lista')
  expect(buttons('Reposto')[0].disabled).toBe(true)
  expect(document.querySelector('.replenishment-dialog')).toBeNull()
  unmount()
  await mount()
  expect(mocks.batch).toHaveBeenCalledWith('batch1')
  expect(root.textContent).toContain('Reposição registrada; etiquetas na fila.')
  expect(mocks.confirm).toHaveBeenCalledTimes(1)
})

it('releases rejected stock snapshots only after a definitive conflict and requires a fresh confirmation', async () => {
  await mount()
  await click('Reposto')
  await check('.confirmation-line input')
  mocks.confirm.mockRejectedValueOnce({
    response: { status: 409, data: { detail: 'O saldo mudou. Confira novamente.' } },
  })
  await click('Confirmar reposição e imprimir')
  expect(sessionStorage.getItem('eleven-replenishment-confirmation:owner')).toBeNull()
  expect(root.textContent).toContain('O saldo mudou')
  expect(document.querySelector('.replenishment-dialog')).toBeNull()
  await click('Reposto')
  expect(buttons('Confirmar reposição e imprimir')[0].disabled).toBe(true)
  expect(mocks.confirm).toHaveBeenCalledTimes(1)
})

it('supports batch quantities, uses the chosen layout revision and refreshes preview on template changes', async () => {
  const standard = standardLabelLayout(),
    custom = { ...standard, id: 'custom', name: 'Roupas', builtin: false, version: 7 }
  mocks.layouts.mockResolvedValue([standard, custom])
  await mount()
  await quantity('3')
  await click('Selecionar esta página')
  await click('Repor selecionados')
  expect(document.querySelector('.review-summary')?.textContent).toContain(
    '2 produtos · 4 unidades · 4 etiquetas',
  )
  await chooseDropdown(
    document.querySelectorAll('.replenishment-dialog .erp-dropdown')[0],
    'custom',
  )
  await flush()
  expect(mocks.preview).toHaveBeenLastCalledWith('p1', { layout_id: 'custom', layout_revision: 7 })
  await chooseDropdown(document.querySelectorAll('.replenishment-dialog .erp-dropdown')[1], 'p2')
  await flush()
  expect(mocks.preview).toHaveBeenLastCalledWith('p2', { layout_id: 'custom', layout_revision: 7 })
  await check('.confirmation-line input')
  await click('Confirmar reposição e imprimir')
  expect(mocks.confirm.mock.calls[0][0]).toMatchObject({
    layout_id: 'custom',
    layout_revision: 7,
    items: [
      { item_id: 'p1', copies: 3 },
      { item_id: 'p2', copies: 1 },
    ],
  })
})

it('blocks new replenishment without a configured printer or a successful preview', async () => {
  mocks.device.mockResolvedValueOnce({ device: null })
  await mount()
  expect(buttons('Reposto')[0].disabled).toBe(true)
  expect(root.textContent).toContain('Configure a Zebra')
  unmount()
  mocks.preview.mockRejectedValueOnce(new Error('preview offline'))
  await mount()
  await click('Reposto')
  expect(buttons('Confirmar reposição e imprimir')[0].disabled).toBe(true)
  expect(document.body.textContent).toContain('Não foi possível preparar a prévia')
  await click('Atualizar prévia')
  expect(document.querySelector('.label-preview img')).not.toBeNull()
})

it('rejects invalid saved requests rather than letting a replacement request overwrite them', async () => {
  sessionStorage.setItem('eleven-replenishment-confirmation:owner', '{bad')
  await mount()
  expect(root.textContent).toContain('confirmação salva que não pôde ser lida')
  expect(buttons('Reposto')[0].disabled).toBe(true)
  expect(mocks.confirm).not.toHaveBeenCalled()
  expect(sessionStorage.getItem('eleven-replenishment-confirmation:owner')).toBe('{bad')
})

it('clears page selection on search and ignores late search responses', async () => {
  await mount()
  await click('Selecionar esta página')
  const first = deferred<{
    items: ReplenishmentProduct[]
    total: number
    page: number
    page_size: number
  }>()
  mocks.list.mockReturnValueOnce(first.promise)
  const input = root.querySelector<HTMLInputElement>('[type=search]')!
  input.value = 'primeira'
  input.dispatchEvent(new Event('input', { bubbles: true }))
  await click('Buscar')
  expect(root.querySelector('.selection-footer')).toBeNull()
  input.value = 'segunda'
  input.dispatchEvent(new Event('input', { bubbles: true }))
  mocks.list.mockResolvedValueOnce({ items: [other], total: 1, page: 1, page_size: 40 })
  await click('Buscar')
  first.resolve({ items: [product], total: 1, page: 1, page_size: 40 })
  await flush()
  expect(root.querySelector('.product-row')?.textContent).toContain(other.name)
  expect(mocks.list.mock.calls[1][2].aborted).toBe(true)
})

it('isolates pending requests and stale responses when the user changes', async () => {
  await mount()
  await click('Reposto')
  await check('.confirmation-line input')
  const pending = deferred<typeof batch>()
  mocks.confirm.mockReturnValueOnce(pending.promise)
  const confirm = buttons('Confirmar reposição e imprimir')[0]
  confirm.click()
  await flush()
  mocks.auth.user.id = 'another-user'
  await flush()
  expect(document.querySelector('.replenishment-dialog')).toBeNull()
  pending.resolve(batch)
  await flush()
  expect(root.textContent).not.toContain('Reposição registrada; etiquetas na fila.')
  expect(sessionStorage.getItem('eleven-replenishment-confirmation:owner')).not.toBeNull()
  expect(sessionStorage.getItem('eleven-replenishment-result:another-user')).toBeNull()
})

it('refreshes on returning to the screen without polling or disturbing an open confirmation', async () => {
  const now = vi.spyOn(Date, 'now').mockReturnValue(100000)
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
  await mount()
  window.dispatchEvent(new Event('focus'))
  await flush()
  expect(mocks.list).toHaveBeenCalledTimes(1)
  now.mockReturnValue(131000)
  window.dispatchEvent(new Event('focus'))
  await flush()
  expect(mocks.list).toHaveBeenCalledTimes(2)
  await click('Reposto')
  now.mockReturnValue(170000)
  window.dispatchEvent(new Event('focus'))
  await flush()
  expect(mocks.list).toHaveBeenCalledTimes(2)
})

it('translates the operational flow into Spanish', async () => {
  await mount('es')
  expect(root.textContent).toContain('Reposición')
  await click('Repuesto')
  expect(document.body.textContent).toContain('Confirmar reposición e imprimir')
})
