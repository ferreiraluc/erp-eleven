import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import ProductLabelLayoutEditor from './ProductLabelLayoutEditor.vue'
import { standardLabelLayout } from '@/test/productLabelDesign'
import { chooseDropdown } from '@/test/dropdown'
import {
  cloneDesign,
  designIssue,
  elementSize,
  labelLayoutReference,
  moveLabelElement,
  type ProductLabelLayout,
} from '@/services/productLabelDesign'

const mocks = vi.hoisted(() => ({
  designPreview: vi.fn(),
  saveLayout: vi.fn(),
  deleteLayout: vi.fn(),
}))
vi.mock('@/services/productLabels', () => ({ productLabels: mocks }))
let app: App, root: HTMLDivElement
const onSaved = vi.fn(),
  onUse = vi.fn()
async function flush() {
  for (let i = 0; i < 4; i++) {
    await Promise.resolve()
    await nextTick()
  }
}
beforeEach(() => {
  vi.resetAllMocks()
  vi.stubGlobal('URL', {
    createObjectURL: vi.fn(() => 'blob:local-design-preview'),
    revokeObjectURL: vi.fn(),
  })
  mocks.designPreview.mockResolvedValue(new Blob(['local-test'], { type: 'image/png' }))
  mocks.saveLayout.mockImplementation(async (id, body) => ({
    id,
    builtin: false,
    ...body,
    version: body.version + 1,
  }))
})
afterEach(() => {
  app?.unmount()
  root?.remove()
  vi.unstubAllGlobals()
})
async function mount(layouts: ProductLabelLayout[] = [standardLabelLayout()]) {
  root = document.createElement('div')
  document.body.append(root)
  app = createApp(ProductLabelLayoutEditor, {
    layouts,
    products: [{ id: 'product-1', name: 'Produto selecionado' }],
    activeId: layouts[0]!.id,
    disabled: false,
    onSaved,
    onUse,
  })
  app.use(createI18n({ legacy: false, locale: 'pt', messages: { pt: {} } }))
  app.mount(root)
  await flush()
  await vi.waitFor(() => expect(mocks.designPreview).toHaveBeenCalled())
  await flush()
}
function button(text: string) {
  return Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find(
    (b) => b.textContent?.trim() === text,
  )!
}
function property(label: string) {
  return Array.from(root.querySelectorAll<HTMLLabelElement>('.design-properties label'))
    .find((l) => l.textContent?.startsWith(label))!
    .querySelector<HTMLInputElement>('input')!
}

it('keeps moves inside the paper and reserves the complete QR quiet zone', () => {
  const config = cloneDesign(standardLabelLayout().config),
    qr = config.elements.find((e) => e.type === 'qr')!
  expect(elementSize(qr)).toEqual({ width: 111, height: 111 })
  moveLabelElement(qr, 999, -10)
  expect([qr.x, qr.y]).toEqual([369, 0])
  expect(designIssue(standardLabelLayout().config)).toBe('')
  const name = config.elements.find((e) => e.id === 'name')!
  name.x = qr.x
  expect(designIssue(config)).toContain('dentro do papel')
  name.x = 300
  if (name.type === 'text') name.width = 150
  expect(designIssue(config)).toContain('área de leitura do QR')
  expect(labelLayoutReference(standardLabelLayout())).toBeUndefined()
})

it('previews selected product data, moves by keyboard, undoes, and saves a new shared model', async () => {
  await mount()
  expect(mocks.designPreview.mock.calls[0][1]).toBe('product-1')
  expect(button('Usar este modelo').disabled).toBe(true) // the editable standard is a new copy
  const name = root.querySelector<HTMLButtonElement>('[aria-label="Mover campo: Nome do produto"]')!
  name.dispatchEvent(
    new KeyboardEvent('keydown', { key: 'ArrowRight', shiftKey: true, bubbles: true }),
  )
  await flush()
  expect(root.textContent).toContain('Alterações não salvas')
  expect(button('Usar este modelo').disabled).toBe(true)
  await vi.waitFor(() =>
    expect(
      mocks.designPreview.mock.lastCall?.[0].elements.find((e: { id: string }) => e.id === 'name')
        .x,
    ).toBe(40),
  )
  button('Desfazer').click()
  await flush()
  await vi.waitFor(() =>
    expect(
      mocks.designPreview.mock.lastCall?.[0].elements.find((e: { id: string }) => e.id === 'name')
        .x,
    ).toBe(32),
  )
  await vi.waitFor(() => expect(button('Salvar como novo').disabled).toBe(false))
  button('Salvar como novo').click()
  await flush()
  expect(mocks.saveLayout).toHaveBeenCalledWith(
    expect.stringMatching(/^product-[a-f0-9]{20}$/),
    expect.objectContaining({ version: 0 }),
  )
  expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ version: 1, builtin: false }))
  expect(root.textContent).toContain('disponível nos outros aparelhos')
})

it('blocks a field covering the QR, and never requests or saves the invalid design', async () => {
  await mount()
  await chooseDropdown(root.querySelector('.design-properties>.erp-dropdown'), 'name')
  await flush()
  const before = mocks.designPreview.mock.calls.length
  const width = property('Largura')
  width.value = '50'
  width.dispatchEvent(new Event('change', { bubbles: true }))
  await flush()
  expect(root.textContent).toContain('Os campos não podem cobrir a área de leitura do QR.')
  expect(button('Salvar como novo').disabled).toBe(true)
  await new Promise((resolve) => setTimeout(resolve, 220))
  expect(mocks.designPreview).toHaveBeenCalledTimes(before)
  expect(mocks.saveLayout).not.toHaveBeenCalled()
})

it('moves a pointer-dragged field in label coordinates at a scaled preview', async () => {
  await mount()
  const canvas = root.querySelector<HTMLElement>('.design-canvas')!
  vi.spyOn(canvas, 'getBoundingClientRect').mockReturnValue({ width: 960, height: 480 } as DOMRect)
  const target = root.querySelector<HTMLButtonElement>(
    '[aria-label="Mover campo: Nome do produto"]',
  )!
  function pointer(type: string, x: number, y: number) {
    const event = new Event(type, { bubbles: true })
    Object.defineProperties(event, {
      pointerId: { value: 1 },
      button: { value: 0 },
      clientX: { value: x },
      clientY: { value: y },
    })
    target.dispatchEvent(event)
  }
  pointer('pointerdown', 64, 120)
  pointer('pointermove', 96, 136)
  pointer('pointerup', 96, 136)
  await flush()
  await vi.waitFor(() =>
    expect(
      mocks.designPreview.mock.lastCall?.[0].elements.find((e: { id: string }) => e.id === 'name'),
    ).toMatchObject({ x: 48, y: 68 }),
  )
  expect(button('Desfazer').disabled).toBe(false)
})

it('preserves the draft and reports a version conflict instead of silently overwriting', async () => {
  const custom = {
    ...standardLabelLayout(),
    id: `product-${'c'.repeat(20)}`,
    name: 'Roupas',
    builtin: false,
    version: 2,
  }
  await mount([custom])
  root
    .querySelector<HTMLButtonElement>('[aria-label="Mover campo: Nome do produto"]')!
    .dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }))
  await flush()
  await vi.waitFor(() => expect(button('Salvar alterações').disabled).toBe(false))
  mocks.saveLayout.mockRejectedValueOnce({
    response: {
      status: 409,
      data: { detail: 'O modelo de etiqueta mudou. Atualize os modelos e confira a prévia.' },
    },
  })
  button('Salvar alterações').click()
  await flush()
  expect(mocks.saveLayout.mock.lastCall?.[1].version).toBe(2)
  expect(root.textContent).toContain('O modelo de etiqueta mudou')
  expect(root.textContent).toContain('Alterações não salvas')
  expect(onSaved).not.toHaveBeenCalled()
})

it('keeps draft changes when switching models until the user explicitly discards them', async () => {
  const standard = standardLabelLayout(),
    custom = {
      ...standard,
      id: `product-${'a'.repeat(20)}`,
      name: 'Calçados',
      builtin: false,
      version: 2,
    }
  await mount([standard, custom])
  button('+ Adicionar campo').click()
  await flush()
  await chooseDropdown(root.querySelector('.design-models>.erp-dropdown'), custom.id)
  await flush()
  expect(root.textContent).toContain('Há alterações não salvas')
  button('Continuar editando').click()
  await flush()
  expect(root.querySelector<HTMLInputElement>('[aria-label="Nome do modelo"]')!.value).toContain(
    'Cópia',
  )
  await chooseDropdown(root.querySelector('.design-models>.erp-dropdown'), custom.id)
  await flush()
  button('Descartar e abrir').click()
  await flush()
  expect(root.querySelector<HTMLInputElement>('[aria-label="Nome do modelo"]')!.value).toBe(
    'Calçados',
  )
  button('Usar este modelo').click()
  await flush()
  expect(onUse).toHaveBeenCalledWith(custom.id)
})
