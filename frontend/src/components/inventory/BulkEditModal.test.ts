import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import BulkEditModal from './BulkEditModal.vue'
import { chooseDropdown } from '@/test/dropdown'

const api = vi.hoisted(() => ({ batchEdit: vi.fn(), getSuppliers: vi.fn() }))
const photos = vi.hoisted(() => ({ prepareGalleryFile: vi.fn(), galleryPreview: vi.fn() }))
const photoEditor = vi.hoisted(() => ({ photoStatus: vi.fn(), cutoutPhoto: vi.fn(), catalogForStorage: vi.fn(), analyzePhoto: vi.fn(), generateCatalog: vi.fn() }))
vi.mock('@/services/api', () => ({ inventoryAPI: api }))
vi.mock('@/services/productGallery', () => photos)
vi.mock('@/services/productPhoto', () => photoEditor)
let app: App, root: HTMLDivElement
const items = [
  { id: 's-white', name: 'Camiseta S Branca', size: 'S', color: 'Branca' },
  { id: 'm-white', name: 'Camiseta M Branca', size: 'M', color: 'branca' },
  { id: 's-blue', name: 'Camiseta P Azul', size: 'P', color: 'Azul' },
].map((item) => ({
  ...item,
  stock_loja: 3,
  stock_deposito: 2,
  current_stock: 5,
  sku_internal: item.id,
  currency: 'USD',
  is_active: true,
}))
const tick = async () => {
  await nextTick()
  await nextTick()
}
function button(label: string) {
  const b = Array.from(document.querySelectorAll<HTMLButtonElement>('button')).find(
    (b) => b.textContent?.trim() === label,
  )
  if (!b) throw new Error(`Missing button: ${label}`)
  return b
}
async function input(selector: string, value: string) {
  const el = root.querySelector<HTMLInputElement>(selector)!
  el.value = value
  el.dispatchEvent(new Event('input', { bubbles: true }))
  await tick()
}
async function choose(label: string, option: string) {
  root.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`)!.click()
  await tick()
  button(option).click()
  await tick()
}
async function field(value: string) {
  await chooseDropdown(root.querySelector('button[aria-label="Campo para editar"]'), value)
}
async function prepare(count = 3) {
  button(`Preparar alteração · ${count}`).click()
  await tick()
}
const quantity = (id: string) => `[data-stock-item="${id}"] input[type=number]`
async function mount(data = items, saved = vi.fn()) {
  root = document.createElement('div')
  document.body.append(root)
  const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, en: {}, es: {} } })
  app = createApp(BulkEditModal, { items: data, onSaved: saved }).use(i18n)
  app.mount(root)
  await tick()
  return i18n
}
beforeEach(() => {
  api.batchEdit.mockResolvedValue({})
  api.getSuppliers.mockResolvedValue([])
  photos.prepareGalleryFile.mockImplementation(async (file: File) => `prepared:${file.name}`)
  photos.galleryPreview.mockImplementation(async (source: string) => `thumb:${source}`)
  photoEditor.photoStatus.mockResolvedValue({ editing_available: false, model: '' })
  photoEditor.cutoutPhoto.mockResolvedValue('background-removed')
  photoEditor.catalogForStorage.mockResolvedValue('edited-photo')
  vi.spyOn(console, 'error').mockImplementation(() => {})
})
afterEach(() => {
  app?.unmount()
  root?.remove()
  vi.restoreAllMocks()
  vi.resetAllMocks()
})

it('uses one review list for batch fields and individual overrides without duplicate sections', async () => {
  await mount()
  expect(root.querySelectorAll('.product-row')).toHaveLength(3)
  expect(root.textContent).not.toContain('Campos compartilhados')
  expect(root.textContent).not.toContain('Campos por item')
  await field('color')
  await input('input[aria-label="Valor para aplicar"]', 'Navy')
  await prepare()
  const colorFields = Array.from(
    root.querySelectorAll<HTMLInputElement>('.row-editor input[aria-label^="Cor de"]'),
  )
  expect(colorFields.map((el) => el.value)).toEqual(['Navy', 'Navy', 'Navy'])
  colorFields[1].value = 'Preta'
  colorFields[1].dispatchEvent(new Event('input', { bubbles: true }))
  await tick()
  await field('description')
  await input('textarea[aria-label="Valor para aplicar"]', 'Placa de metal')
  await prepare()
  await field('color')
  expect(
    root.querySelector<HTMLInputElement>(
      '[data-detail-item="m-white"] .row-editor input[aria-label^="Cor de"]',
    )!.value,
  ).toBe('Preta')
  expect(api.batchEdit).not.toHaveBeenCalled()
  button('Salvar 3 itens').click()
  await tick()
  expect(api.batchEdit.mock.calls[0][0]).toMatchObject({
    sizes: [
      { id: 's-white', color: 'Navy', description: 'Placa de metal' },
      { id: 'm-white', color: 'Preta', description: 'Placa de metal' },
      { id: 's-blue', color: 'Navy', description: 'Placa de metal' },
    ],
    stock_adjustments: [],
  })
})

it('sets counts by color and canonical size, preserving both locations and individual overrides', async () => {
  await mount()
  await field('stock')
  await choose('Operação de quantidade', 'Definir quantidade')
  await choose('Aplicar dados a', 'Cor: branca') // normalized, last display label
  await input('input[aria-label="Quantidade para aplicar"]', '4')
  await prepare(2)
  expect((root.querySelector(quantity('s-blue')) as HTMLInputElement).value).toBe('3')
  await choose('Aplicar dados a', 'Tamanho: S')
  await input('input[aria-label="Quantidade para aplicar"]', '8')
  await prepare(2)
  await input(quantity('s-blue'), '9')
  await choose('Local do ajuste', 'Depósito')
  await input(quantity('m-white'), '0')
  await choose('Local do ajuste', 'Loja')
  expect((root.querySelector(quantity('s-white')) as HTMLInputElement).value).toBe('8')
  expect(root.querySelector('.stock-summary')?.textContent).toContain('25') // 8+4+9 + 2+0+2
  expect(api.batchEdit).not.toHaveBeenCalled()
  button('Salvar 3 itens').click()
  await tick()
  expect(api.batchEdit.mock.calls[0][0].stock_adjustments).toEqual([
    {
      id: 's-white',
      stock_loja: 8,
      stock_deposito: 2,
      expected_loja: 3,
      expected_deposito: 2,
      expected_total: 5,
    },
    {
      id: 'm-white',
      stock_loja: 4,
      stock_deposito: 0,
      expected_loja: 3,
      expected_deposito: 2,
      expected_total: 5,
    },
    {
      id: 's-blue',
      stock_loja: 9,
      stock_deposito: 2,
      expected_loja: 3,
      expected_deposito: 2,
      expected_total: 5,
    },
  ])
})

it('adds/subtracts across a selection atomically and never clips a negative result to zero', async () => {
  await mount()
  await field('stock')
  await choose('Operação de quantidade', 'Somar ou retirar')
  await input('input[aria-label="Quantidade para aplicar"]', '-4')
  await prepare()
  expect(root.textContent).toContain('Nenhuma linha foi alterada')
  expect(
    Array.from(
      root.querySelectorAll<HTMLInputElement>(
        '[data-stock-item] input[aria-label^="Quantidade " ]',
      ),
    ).map((i) => i.value),
  ).toEqual(['3', '3', '3'])
  await input('input[aria-label="Quantidade para aplicar"]', '2')
  await prepare()
  expect(
    Array.from(
      root.querySelectorAll<HTMLInputElement>(
        '[data-stock-item] input[aria-label^="Quantidade " ]',
      ),
    ).map((i) => i.value),
  ).toEqual(['5', '5', '5'])
})

it.each(['', '-1', '1.5', '2147483648'])(
  'blocks invalid final quantity %s without losing the draft',
  async (value) => {
    await mount()
    await input(quantity('s-white'), value)
    button('Salvar 3 itens').click()
    await tick()
    expect(api.batchEdit).not.toHaveBeenCalled()
    expect(root.textContent).toContain('Confira as quantidades')
  },
)

it('preserves known rows when one item is unknown; saves without a reason and shows conflicts', async () => {
  const saved = vi.fn()
  await mount([{ ...items[0], stock_loja: null, current_stock: null } as any, items[1]], saved)
  expect(root.querySelector<HTMLInputElement>(quantity('s-white'))!.disabled).toBe(true)
  await input(quantity('m-white'), '0')
  api.batchEdit.mockRejectedValueOnce({
    response: {
      data: {
        detail:
          'O estoque mudou desde a abertura da edição. Nenhuma alteração foi salva; reabra a edição para conferir os saldos atuais.',
      },
    },
  })
  button('Salvar 2 itens').click()
  await tick()
  expect(saved).not.toHaveBeenCalled()
  expect(root.querySelector('.save-error')?.textContent).toContain('O estoque mudou')
  expect(api.batchEdit.mock.calls[0][0].stock_adjustments).toHaveLength(1)
  expect(root.querySelector<HTMLInputElement>(quantity('m-white'))!.value).toBe('0')
})

it('keeps step buttons from focusing inputs and translates controls in an open editor', async () => {
  const i18n = await mount()
  root
    .querySelector<HTMLButtonElement>(
      '[data-stock-item="s-white"] button[aria-label="Aumentar quantidade"]',
    )!
    .click()
  await tick()
  expect(document.activeElement?.tagName).not.toBe('INPUT')
  expect(root.querySelector<HTMLInputElement>(quantity('s-white'))!.value).toBe('4')
  i18n.global.locale.value = 'es'
  await tick()
  expect(root.textContent).toContain('Datos del producto en lote')
  await field('stock')
  expect(root.textContent).toContain('Motivo del ajuste (opcional)')
})

it('retains the reviewed baseline if the parent refreshes while the editor is open', async () => {
  const rows = reactive([{ ...items[0] }])
  await mount(rows)
  await input(quantity('s-white'), '6')
  rows[0].stock_loja = 7
  rows[0].current_stock = 9
  await tick()
  button('Salvar 1 itens').click()
  await tick()
  expect(api.batchEdit.mock.calls[0][0].stock_adjustments[0]).toMatchObject({
    stock_loja: 6,
    expected_loja: 3,
    expected_total: 5,
  })
})

async function uploadPhoto(name: string) {
  const control = root.querySelector<HTMLInputElement>('[data-bulk-photo-file]')!
  Object.defineProperty(control, 'files', {
    value: [new File(['fixture'], name, { type: 'image/jpeg' })],
    configurable: true,
  })
  control.dispatchEvent(new Event('change', { bubbles: true }))
  await tick()
  await tick()
}
async function photoScope(value: string) {
  await chooseDropdown(root.querySelector('button[aria-label="Aplicar dados a"]'), value)
}

it('edits one uploaded photo and saves the background-removed result for every selected item only on Save', async () => {
  await mount()
  await field('photo')
  await uploadPhoto('all.jpg')
  button('Editar foto').click()
  await vi.dynamicImportSettled()
  await tick()
  expect(button('Salvar 3 itens').disabled).toBe(true)
  button('Remover fundo · grátis').click()
  await tick()
  expect(photoEditor.cutoutPhoto).toHaveBeenCalledWith('prepared:all.jpg', expect.any(AbortSignal))
  button('Usar foto').click()
  await tick(); await tick()
  expect(photoEditor.catalogForStorage).toHaveBeenCalledWith('background-removed')
  expect(document.querySelector('.photo-dialog')).toBeNull()
  expect(api.batchEdit).not.toHaveBeenCalled()
  expect(button('Salvar 3 itens').disabled).toBe(false)
  button('Salvar 3 itens').click()
  await tick()
  expect(api.batchEdit).toHaveBeenCalledTimes(1)
  expect(api.batchEdit.mock.calls[0][0].image_groups).toEqual([
    { item_ids: items.map(item => item.id), image_data: 'edited-photo' },
  ])
  expect(photoEditor.analyzePhoto).not.toHaveBeenCalled()
  expect(photoEditor.generateCatalog).not.toHaveBeenCalled()
})

it('stages one cover per color, includes every size and only saves the selected IDs once', async () => {
  await mount()
  await field('photo')
  await photoScope('color:branco')
  await uploadPhoto('white.jpg')
  await photoScope('color:azul')
  await uploadPhoto('blue.jpg')
  expect(api.batchEdit).not.toHaveBeenCalled()
  expect(root.querySelectorAll('.photo-draft')).toHaveLength(2)
  expect(
    Array.from(root.querySelectorAll('.card-thumb')).map((el) => el.getAttribute('src')),
  ).toEqual(['thumb:prepared:white.jpg', 'thumb:prepared:white.jpg', 'thumb:prepared:blue.jpg'])
  button('Salvar 3 itens').click()
  await tick()
  expect(api.batchEdit.mock.calls[0][0]).toMatchObject({
    item_ids: items.map((item) => item.id),
    stock_adjustments: [],
    image_groups: [
      { item_ids: ['s-white', 'm-white'], image_data: 'prepared:white.jpg' },
      { item_ids: ['s-blue'], image_data: 'prepared:blue.jpg' },
    ],
  })
  expect(api.batchEdit.mock.calls[0][0].image_data).toBeUndefined()
  expect(api.batchEdit.mock.calls[0][0].additional_images).toBeUndefined()
})

it('lets a color override a shared photo and undo preserves other drafts', async () => {
  await mount()
  await field('photo')
  await uploadPhoto('all.jpg')
  await photoScope('color:azul')
  await uploadPhoto('blue.jpg')
  const undo = root.querySelector<HTMLButtonElement>('button[aria-label="Desfazer foto de Azul"]')!
  undo.click()
  await tick()
  expect(root.querySelectorAll('.photo-draft')).toHaveLength(1)
  button('Salvar 3 itens').click()
  await tick()
  expect(api.batchEdit.mock.calls[0][0].image_groups).toEqual([
    { item_ids: ['s-white', 'm-white'], image_data: 'prepared:all.jpg' },
  ])
})

it('keeps photo membership by ID when color changes and ignores file failure without losing drafts', async () => {
  await mount()
  await field('photo')
  await photoScope('color:branco')
  await uploadPhoto('white.jpg')
  await field('color')
  await input('input[aria-label="Valor para aplicar"]', 'Bege')
  await prepare(2)
  await field('photo')
  expect(root.querySelector('.photo-draft')?.textContent).toContain('Bege')
  photos.prepareGalleryFile.mockRejectedValueOnce(new Error('invalid'))
  await uploadPhoto('broken.jpg')
  expect(root.querySelector('.photo-error')?.textContent).toContain('Não foi possível preparar')
  button('Salvar 3 itens').click()
  await tick()
  expect(api.batchEdit.mock.calls[0][0].image_groups).toEqual([
    { item_ids: ['s-white', 'm-white'], image_data: 'prepared:white.jpg' },
  ])
})

it('blocks Save while preparing an image and translates the photo controls', async () => {
  const i18n = await mount()
  let finish!: (value: string) => void
  photos.prepareGalleryFile.mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve
    }),
  )
  await input('textarea[aria-label="Valor para aplicar"]', 'Placa')
  button('Preparar alteração · 3').click()
  await tick()
  await field('photo')
  await uploadPhoto('slow.jpg')
  await field('brand') // decoding must stay mounted and keep Save blocked
  expect(button('Salvar 3 itens').disabled).toBe(true)
  i18n.global.locale.value = 'es'
  await tick()
  expect(root.textContent).toContain('Datos del producto en lote')
  finish('prepared:slow.jpg')
  await tick()
  await tick()
  expect(button('Guardar 3 artículos').disabled).toBe(false)
})

it('appends descriptions by color, permits individual edits and saves only after review', async () => {
  await mount(items.map((item, i) => ({ ...item, description: `Original ${i}` })))
  await chooseDropdown(root.querySelector('button[aria-label="Aplicar dados a"]'), 'color:branco')
  await chooseDropdown(root.querySelector('button[aria-label="Operação dos dados"]'), 'append')
  await input('textarea[aria-label="Valor para aplicar"]', 'Placa de metal')
  button('Preparar alteração · 2').click()
  await tick()
  expect(
    root.querySelector<HTMLTextAreaElement>('[data-detail-item="s-white"] textarea')!.value,
  ).toBe('Original 0\nPlaca de metal')
  expect(
    root.querySelector<HTMLTextAreaElement>('[data-detail-item="s-blue"] textarea')!.value,
  ).toBe('Original 2')
  await input('[data-detail-item="m-white"] textarea', 'Logo emborrachado')
  expect(api.batchEdit).not.toHaveBeenCalled()
  button('Salvar 3 itens').click()
  await tick()
  expect(api.batchEdit.mock.calls[0][0]).toMatchObject({
    details: true,
    sizes: [
      { id: 's-white', description: 'Original 0\nPlaca de metal' },
      { id: 'm-white', description: 'Logo emborrachado' },
    ],
  })
})

it('clears descriptions explicitly without erasing other fields', async () => {
  await mount(items.map((item) => ({ ...item, description: 'Antiga' })))
  await chooseDropdown(root.querySelector('button[aria-label="Operação dos dados"]'), 'clear')
  button('Preparar alteração · 3').click()
  await tick()
  button('Salvar 3 itens').click()
  await tick()
  expect(api.batchEdit.mock.calls[0][0].sizes).toEqual(
    items.map((item) => ({ id: item.id, description: '' })),
  )
})

it('reviews base plus canonical sizes, preserves leading zeros and permits one barcode per item', async () => {
  await mount()
  await field('barcode')
  await input('input[aria-label="Código base"]', '00123')
  button('Conferir códigos').click()
  await tick()
  expect(root.querySelector('.barcode-preview')!.textContent).toContain('00123S')
  expect(api.batchEdit).not.toHaveBeenCalled()
  button('Aplicar códigos à prévia').click()
  await tick()
  await input('input[aria-label="Código do item em leitura"]', '00099')
  root
    .querySelector('input[aria-label="Código do item em leitura"]')!
    .dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
  await tick()
  expect(
    root.querySelector<HTMLInputElement>('input[aria-label="Código do item em leitura"]')!.value,
  ).toBe('00123M')
  await input('input[aria-label="Código do item em leitura"]', '00088')
  button('Salvar 3 itens').click()
  await tick()
  expect(api.batchEdit.mock.calls[0][0].sizes).toEqual([
    { id: 's-white', barcode: '00099' },
    { id: 'm-white', barcode: '00088' },
    { id: 's-blue', barcode: '00123S' },
  ])
})

it('prevents an old barcode preview from overwriting a manual scan', async () => {
  await mount()
  await field('barcode')
  await input('input[aria-label="Código base"]', '00123')
  button('Conferir códigos').click()
  await tick()
  await input('input[aria-label="Código do item em leitura"]', '00099')
  expect(root.querySelector('.barcode-preview')).toBeNull()
  button('Salvar 3 itens').click()
  await tick()
  expect(api.batchEdit.mock.calls[0][0].sizes).toEqual([{ id: 's-white', barcode: '00099' }])
})

it('pairs price and currency, scopes by color and preserves individual overrides across fields', async () => {
  await mount(
    items.map((item) => ({
      ...item,
      sale_price: 15,
      sale_currency: 'USD',
      cost_price: 5,
      cost_currency: 'BRL',
    })),
  )
  await field('sale')
  await chooseDropdown(root.querySelector('button[aria-label="Aplicar dados a"]'), 'color:branco')
  await chooseDropdown(root.querySelector('button[aria-label="Moeda para aplicar"]'), 'EUR')
  await input('input[aria-label="Preço para aplicar"]', '22.50')
  await prepare(2)
  await input('[data-detail-item="m-white"] input[aria-label^="Preço de"]', '25')
  await field('cost')
  await input('input[aria-label="Preço para aplicar"]', '7')
  await prepare(2)
  await field('sale')
  expect(
    root.querySelector<HTMLInputElement>(
      '[data-detail-item="s-blue"] input[aria-label^="Preço de"]',
    )!.value,
  ).toBe('15')
  button('Salvar 3 itens').click()
  await tick()
  expect(api.batchEdit.mock.calls[0][0].sizes).toEqual([
    { id: 's-white', sale_price: 22.5, sale_currency: 'EUR', cost_price: 7 },
    { id: 'm-white', sale_price: 25, sale_currency: 'EUR', cost_price: 7 },
  ])
})

it('applies stock limits without resetting quantities, rejects invalid limits and preserves changes on failure', async () => {
  await mount()
  await field('stock')
  await input('input[aria-label="Mínimo para aplicar"]', '2')
  await input('input[aria-label="Máximo para aplicar"]', '1')
  await prepare()
  expect(root.textContent).toContain('Mínimo não pode ser maior que máximo')
  expect(root.querySelector<HTMLInputElement>(quantity('s-white'))!.value).toBe('3')
  await input('input[aria-label="Máximo para aplicar"]', '10')
  await prepare()
  button('Salvar 3 itens').click()
  await tick()
  expect(api.batchEdit.mock.calls[0][0]).toMatchObject({
    stock_adjustments: [],
    sizes: items.map((item) => ({ id: item.id, min_stock: 2, max_stock: 10 })),
  })
})

it('offers category and subcategory together and preserves a cleared category without changing other fields', async () => {
  await mount(items.map((item) => ({ ...item, category: 'Roupas > Camisetas' })))
  await field('category')
  await chooseDropdown(
    root.querySelector('button[aria-label="Categoria para aplicar · Categoria"]'),
    'Roupas',
  )
  await chooseDropdown(
    root.querySelector('button[aria-label="Categoria para aplicar · Subcategoria"]'),
    'Camisetas',
  )
  await chooseDropdown(root.querySelector('button[aria-label="Operação dos dados"]'), 'clear')
  await prepare()
  button('Salvar 3 itens').click()
  await tick()
  expect(api.batchEdit.mock.calls[0][0].sizes).toEqual(
    items.map((item) => ({ id: item.id, category: '' })),
  )
})

it('corrects only the chosen name fragment, keeping sizes and other drafts in the same review', async () => {
  await mount(
    items.map((item) => ({ ...item, name: item.name.replace('Camiseta', 'T-shirt Biss Y-26-09') })),
  )
  await field('name_replace')
  await input('input[aria-label="Localizar no nome"]', 'Biss')
  await input('input[aria-label="Substituir por"]', 'Boss')
  await prepare()
  await field('brand')
  await input('input[aria-label="Valor para aplicar"]', 'Boss')
  await prepare()
  button('Salvar 3 itens').click()
  await tick()
  expect(api.batchEdit.mock.calls[0][0].sizes).toEqual(
    items.map((item) => ({
      id: item.id,
      name: item.name.replace('Camiseta', 'T-shirt Boss Y-26-09'),
      brand: 'Boss',
    })),
  )
})

it('stages gallery additions by color and sends concurrency versions for every photo recipient', async () => {
  await mount(items.map((item) => ({ ...item, updated_at: '2026-10-26T15:00:00Z' })))
  await field('photo')
  await photoScope('color:azul')
  await chooseDropdown(root.querySelector('button[aria-label="Operação da foto"]'), 'add')
  await uploadPhoto('extra.jpg')
  expect(root.querySelector('[data-detail-item="s-blue"]')!.textContent).toContain(
    'Foto a adicionar',
  )
  button('Salvar 3 itens').click()
  await tick()
  expect(api.batchEdit.mock.calls[0][0]).toMatchObject({
    image_groups: [{ item_ids: ['s-blue'], image_data: 'prepared:extra.jpg', operation: 'add' }],
    sizes: [{ id: 's-blue', expected_updated_at: '2026-10-26T15:00:00Z' }],
  })
})
