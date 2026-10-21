import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import { createRouter, createMemoryHistory } from 'vue-router'
import ProductLabelsView from './ProductLabelsView.vue'
import { labelRequest, mergeLabelSelection, type LabelProduct } from '@/services/productLabels'
import { chooseDropdown } from '@/test/dropdown'

const mocks = vi.hoisted(() => ({
  device: vi.fn(),
  configure: vi.fn(),
  catalog: vi.fn(),
  selection: vi.fn(),
  preview: vi.fn(),
  enqueue: vi.fn(),
  batch: vi.fn(),
  history: vi.fn(),
  cancel: vi.fn(),
  installer: vi.fn(),
}))
vi.mock('@/services/productLabels', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/productLabels')>()),
  productLabels: mocks,
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ isOwner: true, user: { id: 'owner' } }) }))
vi.mock('@/directives/erpDialog', () => ({ vErpDialog: {} }))
vi.mock('@/components/inventory/BarcodeScanner.vue', () => ({ default: { template: '<div />' } }))
const product: LabelProduct = {
  id: 'p1',
  name: 'Camiseta branca S',
  inventory_code: 'INV-A7K4P2',
  size: 'S',
  color: 'Branco',
  group_key: 'Camiseta',
  stock_loja: 4,
  stock_deposito: 2,
  current_stock: 6,
}
const other = {
  ...product,
  id: 'p2',
  name: 'Camiseta azul M',
  inventory_code: 'INV-B7K4P2',
  size: 'M',
  color: 'Azul',
}
const batch = {
  id: 'batch',
  request_key: 'key',
  total: 1,
  jobs: [
    { id: 'j1', name: product.name, code: product.inventory_code, copies: 1, status: 'pending' },
  ],
}
let app: App, root: HTMLDivElement
async function flush() {
  for (let i = 0; i < 6; i++) {
    await Promise.resolve()
    await nextTick()
  }
}
beforeEach(() => {
  vi.resetAllMocks()
  sessionStorage.clear()
  window.history.replaceState({}, '')
  mocks.device.mockResolvedValue({ device: { id: 'zebra', name: 'Zebra ZD220' } })
  mocks.catalog.mockResolvedValue({ items: [product, other], total: 2 })
  mocks.selection.mockResolvedValue([product, other])
  mocks.history.mockResolvedValue([])
  mocks.batch.mockResolvedValue(batch)
  mocks.enqueue.mockResolvedValue(batch)
})
afterEach(() => {
  app?.unmount()
  root?.remove()
})
async function mount() {
  root = document.createElement('div')
  document.body.append(root)
  app = createApp(ProductLabelsView)
  app.use(createI18n({ legacy: false, locale: 'pt', messages: { pt: {} } }))
  app.config.globalProperties.$router = createRouter({ history: createMemoryHistory(), routes: [] })
  app.mount(root)
  await flush()
}
async function click(text: string) {
  const button = Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find(
    (b) => b.textContent?.trim() === text,
  )!
  expect(button, text).toBeTruthy()
  button.click()
  await flush()
}
async function checked(selector: string) {
  const input = root.querySelector<HTMLInputElement>(selector)!
  input.checked = true
  input.dispatchEvent(new Event('change', { bubbles: true }))
  await flush()
}

it('merges grades/lots without multiplying quantities for overlapping products', () => {
  expect(mergeLabelSelection([{ ...product, copies: 4 }], [product, other])).toEqual([
    { ...product, copies: 4 },
    { ...other, copies: 1 },
  ])
  expect(() => labelRequest([{ ...product, copies: 0 }], 'key')).toThrow()
  expect(() => labelRequest([{ ...product, copies: 1.5 }], 'key')).toThrow()
  expect(labelRequest([{ ...product, copies: 3 }], 'key').items[0]).toMatchObject({
    code: 'INV-A7K4P2',
    copies: 3,
  })
})

it('opens selected inventory products, adjusts quantities by color, and requires confirmation', async () => {
  window.history.replaceState({ labelItemIds: ['p1', 'p2'] }, '')
  await mount()
  expect(mocks.selection).toHaveBeenCalledWith({ item_ids: ['p1', 'p2'] })
  const dropdowns = root.querySelectorAll('.quantity-toolbar .erp-dropdown')
  await chooseDropdown(dropdowns[0], 'color:Azul')
  await flush()
  const quantity = root.querySelector<HTMLInputElement>('.quantity-toolbar>input')!
  quantity.value = '8'
  quantity.dispatchEvent(new Event('input', { bubbles: true }))
  await flush()
  await click('Aplicar')
  expect(
    Array.from(root.querySelectorAll<HTMLInputElement>('.stepper input')).map((i) => i.value),
  ).toEqual(['1', '8'])
  expect(mocks.enqueue).not.toHaveBeenCalled()
  await checked('.labels-confirm input[type=checkbox]')
  await click('Imprimir 9 etiquetas')
  expect(mocks.enqueue).toHaveBeenCalledTimes(1)
  expect(mocks.enqueue.mock.calls[0][0].items.map((i: { copies: number }) => i.copies)).toEqual([
    1, 8,
  ])
  expect(root.textContent).toContain('Fila de etiquetas')
})

it('lost response locks editing and persists the same confirmation across a reload', async () => {
  window.history.replaceState({ labelItemIds: ['p1'] }, '')
  mocks.selection.mockResolvedValue([product])
  mocks.enqueue.mockRejectedValueOnce(new Error('Network error'))
  await mount()
  await checked('.labels-confirm input[type=checkbox]')
  await click('Imprimir 1 etiquetas')
  const original = mocks.enqueue.mock.calls[0][0]
  expect(root.querySelector('fieldset')?.disabled).toBe(true)
  expect(JSON.parse(sessionStorage.getItem('eleven-label-confirmation:owner')!)).toEqual(original)
  app.unmount()
  root.remove()
  await mount()
  await click('Recuperar confirmação')
  expect(mocks.enqueue.mock.calls[1][0]).toEqual(original)
  expect(sessionStorage.getItem('eleven-label-confirmation:owner')).toBeNull()
})

it('adds a full grade through the selector without creating or printing products', async () => {
  await mount()
  mocks.catalog.mockResolvedValue({
    items: [{ group_key: 'Camiseta', name: 'Camiseta', count: 2 }],
    total: 1,
  })
  await chooseDropdown(root.querySelector('.labels-search .erp-dropdown')!, 'grades')
  await flush()
  await click('Adicionar todos')
  expect(mocks.selection).toHaveBeenCalledWith({ group_keys: ['Camiseta'] })
  expect(mocks.enqueue).not.toHaveBeenCalled()
  expect(root.querySelector('.labels-tabs span')?.textContent?.trim()).toBe('2')
})
