import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import ItemFormModal from './ItemFormModal.vue'
import { mergeIntake } from '@/services/productIntake'

const mock = vi.hoisted(() => ({ photo: {} as Record<string, unknown>, label: {} as Record<string, unknown>,
  createItem: vi.fn(), createGrade: vi.fn(), createMovement: vi.fn(), getByBarcode: vi.fn() }))
vi.mock('@/services/api', () => ({ inventoryAPI: mock, ocrAPI: {} }))
vi.mock('./ProductPhotoAssistant.vue', async () => {
  const { defineComponent, h } = await import('vue')
  return { default: defineComponent({ props: ['open', 'draft'], emits: ['result', 'close'], setup(props, { emit }) {
    return () => props.open ? h('button', { onClick: () => emit('result', mock.photo) }, 'fixture photo') : null
  } }) }
})
vi.mock('./OcrScanner.vue', async () => {
  const { defineComponent, h } = await import('vue')
  return { default: defineComponent({ props: ['open', 'draft'], emits: ['result', 'close'], setup(props, { emit }) {
    return () => props.open ? h('div', [h('button', { onClick: () => emit('result', mock.label) }, 'fixture label'),
      h('button', { onClick: () => emit('close') }, 'fixture unavailable')]) : null
  } }) }
})
let app: App, root: HTMLDivElement
const button = (text: string) => {
  const b = Array.from(root.querySelectorAll('button')).find(b => b.textContent?.trim() === text)
  if (!b) throw Error(`Missing button: ${text}`)
  return b
}
const input = (label: string) => {
  const group = Array.from(root.querySelectorAll('.form-group')).find(g => g.querySelector('label')?.textContent?.trim() === label)
  if (!group) throw Error(`Missing field: ${label}`)
  return group.querySelector('input') as HTMLInputElement
}
async function setField(label: string, value: string) {
  const el = input(label); el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); await nextTick()
}
async function click(text: string) { button(text).click(); await nextTick(); await nextTick() }
async function mount() {
  root = document.createElement('div'); document.body.append(root)
  const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp(ItemFormModal).use(i18n); app.mount(root); await nextTick()
  return i18n
}
async function review() {
  const el = root.querySelector('.intake-review-check input') as HTMLInputElement
  el.checked = true; el.dispatchEvent(new Event('change', { bubbles: true })); await nextTick()
  await click('Continuar para estoque')
}
beforeEach(() => {
  localStorage.clear()
  mock.photo = { name: 'Polo', description: 'Polo lisa', brand: '', size: '', category: 'Camisetas', color: 'Branco', image_data: 'data:image/jpeg;base64,photo' }
  mock.label = { name: 'Polo', brand: 'Marca da etiqueta', size: 'P', barcode: '4006381333931', sale_price: 50, currency: 'USD' }
  mock.getByBarcode.mockResolvedValue([])
  mock.createItem.mockResolvedValue({ id: 'fixture', name: 'Polo', sku_internal: 'QA-1' })
  mock.createMovement.mockResolvedValue({})
  mock.createGrade.mockResolvedValue({ items: [{ id: 'grade-1' }], total_created: 5 })
})
afterEach(() => { app?.unmount(); root?.remove(); vi.resetAllMocks() })

describe('Unified optional photo and label intake', () => {
  it.each(['photo-first', 'label-first'])('combines complementary evidence in either order: %s', async order => {
    await mount()
    const photo = async () => { await click('Adicionar foto'); await click('fixture photo') }
    const label = async () => { await click('Ler etiqueta'); await click('fixture label') }
    if (order === 'photo-first') { await photo(); await label() } else { await label(); await photo() }
    expect(mock.createItem).not.toHaveBeenCalled()
    await click('Conferir dados')
    expect(input('Nome *').value).toBe('Polo'); expect(input('Marca').value).toBe('Marca da etiqueta')
    expect(input('Tamanho').value).toBe('P'); expect(input('Cor').value).toBe('Branco')
    expect(input('Preço de Venda').value).toBe('50')
    expect(root.querySelector('.intake-conflicts')).toBeNull()
    await review(); await setField('Estoque inicial', '3'); await click('Criar')
    expect(mock.createItem).toHaveBeenCalledTimes(1)
    expect(mock.createGrade).not.toHaveBeenCalled()
    expect(mock.createItem).toHaveBeenCalledWith(expect.objectContaining({ size: 'P', color: 'Branco', barcode: '4006381333931', image_data: mock.photo.image_data, sale_currency: 'USD' }))
    expect(mock.createMovement).toHaveBeenCalledWith(expect.objectContaining({ quantity: 3, location: 'loja' }))
  })
  it('preserves manual corrections and offers an explicit choice for conflicting brand and price/currency', async () => {
    mock.label = { ...mock.label, currency: 'BRL' }
    await mount(); await click('Conferir dados')
    await setField('Nome *', 'Nome escolhido'); await setField('Marca', 'Marca manual'); await setField('Preço de Venda', '99')
    await click('Foto e etiqueta'); await click('Ler etiqueta'); await click('fixture label'); await click('Conferir dados')
    expect(input('Nome *').value).toBe('Nome escolhido'); expect(input('Marca').value).toBe('Marca manual')
    expect(input('Preço de Venda').value).toBe('99')
    expect((root.querySelector('.intake-review-check input') as HTMLInputElement).disabled).toBe(true)
    await click('Manter formulário: Nome escolhido'); await click('Usar etiqueta: Marca da etiqueta'); await click('Usar etiqueta: BRL 50')
    expect(input('Marca').value).toBe('Marca da etiqueta'); expect(input('Preço de Venda').value).toBe('50')
    expect((root.querySelectorAll('.currency-select')[1] as HTMLSelectElement).value).toBe('BRL')
    await setField('Marca', 'Correção final')
    await click('Foto e etiqueta'); await click('Rever etiqueta'); await click('fixture label'); await click('Conferir dados')
    expect(input('Marca').value).toBe('Correção final'); expect(root.querySelector('.intake-conflicts')).toBeNull()
    await review(); await click('2 · Conferência'); await setField('Nome *', 'Alterado depois')
    await click('3 · Estoque'); expect(button('Criar').disabled).toBe(true)
  })
  it('allows manual-only registration and refuses to skip review', async () => {
    await mount(); await click('3 · Estoque'); expect(button('Criar').disabled).toBe(true)
    await click('2 · Conferência'); await setField('Nome *', 'Peça manual'); await review(); await click('Criar')
    expect(mock.createItem).toHaveBeenCalledWith(expect.objectContaining({ name: 'Peça manual', image_data: null }))
    expect(mock.createMovement).not.toHaveBeenCalled()
  })
  it('keeps photo suggestions after an unavailable/cancelled label and permits photo-only registration', async () => {
    await mount(); await click('Adicionar foto'); await click('fixture photo'); await click('Ler etiqueta'); await click('fixture unavailable')
    await click('Conferir dados'); expect(input('Nome *').value).toBe('Polo')
    await review(); await click('Criar')
    expect(mock.createItem).toHaveBeenCalledWith(expect.objectContaining({ name: 'Polo', image_data: mock.photo.image_data }))
  })
  it('creates the explicitly selected grade with shared photo/color and a size-suffixed barcode, never automatic stock', async () => {
    await mount(); await click('Adicionar foto'); await click('fixture photo'); await click('Ler etiqueta'); await click('fixture label')
    await click('Conferir dados'); await review()
    expect(button('Criar')).toBeDefined(); expect(mock.createGrade).not.toHaveBeenCalled()
    await click('Criar grade deste modelo'); await click('P → 2XL')
    expect(root.textContent).toContain('5 produto(s), 0 unidade(s)')
    for (const size of ['P', 'M', 'L', 'XL', '2XL']) expect(root.textContent).toContain('4006381333931' + size)
    await click('Criar grade (5 itens)')
    expect(mock.createGrade).toHaveBeenCalledWith(expect.objectContaining({ sizes: ['P', 'M', 'L', 'XL', '2XL'], color: 'Branco', initial_stock: 0, image_data: mock.photo.image_data, base_barcode: '4006381333931' }))
    expect(mock.createItem).not.toHaveBeenCalled(); expect(mock.createMovement).not.toHaveBeenCalled()
  })
  it('supports label-only input, preserves the base size when selecting another preset, and cancels grade without losing fields', async () => {
    mock.label = { ...mock.label, size: '3XL', color: 'Branco' }
    const i18n = await mount(); await click('Ler etiqueta'); await click('fixture label'); await click('Conferir dados'); await review()
    await click('Criar grade deste modelo'); await click('P → 2XL')
    expect(button('Criar grade (6 itens)')).toBeDefined()
    await click('Cadastrar apenas esta peça'); expect(button('Criar')).toBeDefined()
    i18n.global.locale.value = 'en'; await nextTick(); expect(button('Create variants of this model')).toBeDefined()
    i18n.global.locale.value = 'pt'; await nextTick(); await click('Criar')
    expect(mock.createItem).toHaveBeenCalledWith(expect.objectContaining({ size: '3XL', color: 'Branco', image_data: null }))
    expect(mock.createGrade).not.toHaveBeenCalled()
  })
  it('also adds the base size to barcodes when only additional colors are requested', async () => {
    await mount(); await click('Ler etiqueta'); await click('fixture label'); await click('Conferir dados'); await review()
    await click('Criar grade deste modelo'); await click('Branco'); await click('Preto'); await click('Criar grade (2 itens)')
    expect(mock.createItem).toHaveBeenCalledTimes(2)
    for (const [payload] of mock.createItem.mock.calls) {
      expect(payload).toMatchObject({ size: 'P', barcode: '4006381333931P' })
    }
    expect(mock.createGrade).not.toHaveBeenCalled()
  })
  it('only merges permitted suggestions, never a stock balance, SKU or identity from an AI payload', () => {
    const result = mergeIntake({ name: 'Polo' }, { name: 'Polo', brand: 'Marca', quantity: 20, sku_internal: 'unsafe' } as any, 'photo')
    expect(result.additions).toEqual({ brand: 'Marca' }); expect(result.conflicts).toEqual([])
  })
})
