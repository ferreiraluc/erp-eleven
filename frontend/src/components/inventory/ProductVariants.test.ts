import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import ProductVariantsModal from './ProductVariantsModal.vue'
import ItemFormModal from './ItemFormModal.vue'
import type { InventoryItem } from '@/services/api'
const api = vi.hoisted(() => ({ context: vi.fn(), create: vi.fn() }))
vi.mock('@/services/api', () => ({
  inventoryAPI: { getByBarcode: vi.fn().mockResolvedValue([]) },
  ocrAPI: {},
}))
vi.mock('@/services/inventoryVariants', () => ({ inventoryVariantsAPI: api }))
let app: App, root: HTMLDivElement
const saved = vi.fn()
const fixture = () => ({
  source: {
    id: 'source',
    name: 'Camiseta S',
    size: 'S',
    color: 'Branco',
    barcode: '123S',
    image_data: 'data:image/png;base64,fixture',
  },
  source_version: 'a'.repeat(64),
  model_name: 'Camiseta',
  existing: [{ id: 'source', size: 'S', color: 'Branco' }],
})
const flush = async () => {
  await nextTick()
  await Promise.resolve()
  await nextTick()
}
async function mount() {
  root = document.createElement('div')
  document.body.append(root)
  app = createApp(ProductVariantsModal, { itemId: 'source', mode: 'grade', onSaved: saved }).use(
    createI18n({ legacy: false, locale: 'pt', messages: { pt: {} } }),
  )
  app.mount(root)
  await flush()
}
async function click(text: string) {
  const b = Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find(
    (b) => b.textContent?.trim() === text,
  )
  expect(b, text).toBeTruthy()
  b!.click()
  await flush()
}
async function value(selector: string, value: string) {
  const input = root.querySelector<HTMLInputElement>(selector)!
  expect(input, selector).toBeTruthy()
  input.value = value
  input.dispatchEvent(new Event('input', { bubbles: true }))
  await flush()
}
async function confirm() {
  const input = root.querySelector<HTMLInputElement>('.variant-confirm input')!
  input.checked = true
  input.dispatchEvent(new Event('change', { bubbles: true }))
  await flush()
}
async function submit() {
  const b = root.querySelector<HTMLButtonElement>('.modal-footer .btn-primary')!
  expect(b).toBeTruthy()
  b.click()
  await flush()
}
beforeEach(() => {
  localStorage.clear()
  api.context.mockResolvedValue(fixture())
  api.create.mockResolvedValue({
    created: [{ id: 'new', size: 'M' }],
    existing: [],
    group_key: 'group',
  })
})
afterEach(() => {
  app?.unmount()
  root?.remove()
  vi.resetAllMocks()
})
it('uses the shared editor with presets, colors, per-variant amounts and removals; preserves existing source', async () => {
  await mount()
  expect(api.context).toHaveBeenCalledWith('source', true)
  expect(root.querySelector('img')?.src).toContain('base64,fixture')
  await click('S → 2XL')
  await submit()
  expect(api.create).not.toHaveBeenCalled()
  await click('Preto')
  expect(root.querySelectorAll('.gp-row')).toHaveLength(9)
  await value('[aria-label="Quantidade M Branco"]', '3')
  await value('[aria-label="Quantidade L Preto"]', '8')
  root.querySelector<HTMLButtonElement>('[aria-label="Remover variação XL Preto"]')!.click()
  await flush()
  await confirm()
  await submit()
  const request = api.create.mock.calls[0][1]
  expect(request.variants).toHaveLength(8)
  expect(request.variants).toContainEqual({ size: 'M', color: 'Branco', quantity: 3 })
  expect(request.variants).toContainEqual({ size: 'L', color: 'Preto', quantity: 8 })
  expect(request.variants).not.toContainEqual(
    expect.objectContaining({ size: 'S', color: 'Branco' }),
  )
  expect(request.variants).not.toContainEqual(
    expect.objectContaining({ size: 'XL', color: 'Preto' }),
  )
  expect(request).toMatchObject({
    model_name: 'Camiseta',
    base_barcode: null,
    source_version: 'a'.repeat(64),
    stock_location: 'loja',
    confirm: true,
  })
  expect(saved).toHaveBeenCalledOnce()
})
it('invalidates review when quantities change and rejects invalid or empty matrices', async () => {
  await mount()
  await confirm()
  await submit()
  expect(api.create).not.toHaveBeenCalled()
  await click('S → 2XL')
  await confirm()
  await value('[aria-label="Quantidade M Branco"]', '-1')
  expect(root.querySelector<HTMLInputElement>('.variant-confirm input')!.checked).toBe(false)
  await confirm()
  await submit()
  expect(api.create).not.toHaveBeenCalled()
})
it('supports saved/hidden presets and colors with the same option editor', async () => {
  localStorage.setItem('inv_grade_hidden_presets', JSON.stringify(['p → 2xl']))
  await mount()
  expect(root.textContent).not.toContain('S → 2XL')
  await click('Editar opções')
  expect(root.querySelector('[aria-label="Remover cor Preto"]')).not.toBeNull()
})
it('requires a new server preview after uncertain creation, never immediately repeats stock', async () => {
  api.create.mockRejectedValueOnce(new Error('network'))
  await mount()
  await click('S → 2XL')
  await confirm()
  await submit()
  expect(root.textContent).toContain('Confira os tamanhos cadastrados')
  expect(root.querySelector('.intake-grade')?.hasAttribute('inert')).toBe(true)
  api.context.mockResolvedValueOnce({
    ...fixture(),
    existing: ['S', 'M', 'L', 'XL', '2XL'].map((size) => ({ id: size, size, color: 'Branco' })),
  })
  await click('Conferir tamanhos cadastrados')
  await click('S → 2XL')
  await confirm()
  await submit()
  expect(api.create).toHaveBeenCalledTimes(1)
})
it('opening and cancelling either child preserves unsaved original edits', async () => {
  root = document.createElement('div')
  document.body.append(root)
  app = createApp(ItemFormModal, {
    item: {
      ...fixture().source,
      sku_internal: 'FIXTURE',
      is_active: true,
      current_stock: 7,
      stock_loja: 7,
      stock_deposito: 0,
    } as InventoryItem,
    canCreateVariants: true,
  }).use(createI18n({ legacy: false, locale: 'pt', messages: { pt: {} } }))
  app.mount(root)
  await flush()
  const overlay = root.querySelector('.modal-overlay')!
  await value('.form-group input', 'Edição ainda não salva')
  for (const title of ['Duplicar produto', 'Adicionar grade']) {
    await click(title)
    expect(overlay.getAttribute('style')).toContain('display: none')
    const child = root.querySelector('.intake-modal')!
    expect(child.querySelector('h2')?.textContent).toBe(title)
    Array.from(child.querySelectorAll<HTMLButtonElement>('button'))
      .find((b) => b.textContent?.trim() === 'Cancelar')!
      .click()
    await flush()
    expect((root.querySelector('.form-group input') as HTMLInputElement).value).toBe(
      'Edição ainda não salva',
    )
  }
  expect(api.create).not.toHaveBeenCalled()
})
