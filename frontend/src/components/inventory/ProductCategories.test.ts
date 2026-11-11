import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import ItemFormModal from './ItemFormModal.vue'
import { chooseDropdown, openDropdown } from '@/test/dropdown'

const api = vi.hoisted(() => ({
  getDistinctValues: vi.fn(), getItemPhotos: vi.fn(), getByBarcode: vi.fn(),
  createItem: vi.fn(), updateItem: vi.fn(), duplicate: vi.fn(),
  photo: { category: 'Coleção Especial>Verão>Praia' },
}))
vi.mock('@/services/api', () => ({ inventoryAPI: api, ocrAPI: {} }))
vi.mock('@/services/inventoryVariants', () => ({ inventoryVariantsAPI: { duplicate: api.duplicate } }))
vi.mock('./ProductPhotoAssistant.vue', async () => {
  const { defineComponent, h } = await import('vue')
  return { default: defineComponent({ props: ['open'], emits: ['result'], setup(props, { emit }) {
    return () => props.open ? h('button', { onClick: () => emit('result', api.photo) }, 'Apply photo fixture') : null
  } }) }
})
let app: App, root: HTMLDivElement
const item = { id: 'category-fixture', name: 'Produto de teste', sku_internal: 'FIXTURE',
  current_stock: 0, stock_loja: 0, stock_deposito: 0, cost_price: 0, sale_price: 0,
  currency: 'USD', unit: 'un', is_active: true, category: 'Coleção Especial>Verão>Praia' }
const flush = async () => { await nextTick(); await Promise.resolve(); await nextTick() }
const control = (label: string) => root.querySelector<HTMLInputElement>(`input[role=combobox][aria-label="${label}"]`)!
const dropdown = (label: string) => control(label).closest('.erp-dropdown')!
const button = (text: string) => Array.from(root.querySelectorAll('button')).find(b => b.textContent?.trim() === text)!
async function click(text: string) { expect(button(text), text).toBeTruthy(); button(text).click(); await flush() }
async function type(label: string, value: string) {
  const input = control(label); input.value = value
  input.dispatchEvent(new Event('input', { bubbles: true })); await flush()
}
async function mount(props: Record<string, unknown> = {}) {
  root = document.createElement('div'); document.body.append(root)
  const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp(ItemFormModal, props).use(i18n); app.mount(root); await flush()
  if (!props.item && !props.duplicateContext && !props.gradeContext) await click('Conferir dados')
  return i18n
}
async function saveNew() {
  const name = root.querySelector<HTMLInputElement>('input[placeholder="Nome do produto"]')!
  if (!name.value) { name.value = item.name; name.dispatchEvent(new Event('input', { bubbles: true })); await flush() }
  const check = root.querySelector<HTMLInputElement>('.intake-review-check input')!
  check.checked = true; check.dispatchEvent(new Event('change', { bubbles: true })); await flush()
  await click('Continuar para estoque'); await click('Criar')
}
beforeEach(() => {
  localStorage.clear()
  api.getDistinctValues.mockResolvedValue({ brands: [], categories: [
    'Camisetas>Manga Longa', 'Camisetas>Polo', 'CALÇADOS>Sociais', 'Calçados>Tênis>Corrida',
    'Coleção Especial>Verão>Praia', 'Outros', 'Outra', 'Camisas Sociais',
  ] })
  api.getItemPhotos.mockResolvedValue({ additional_images: [] })
  api.getByBarcode.mockResolvedValue([])
  api.createItem.mockResolvedValue(item); api.updateItem.mockResolvedValue(item); api.duplicate.mockResolvedValue({ ...item, id: 'copy' })
})
afterEach(() => { app?.unmount(); root?.remove(); vi.resetAllMocks() })

describe('Catalog category and subcategory inputs', () => {
  it('lists the catalog roots, scopes children to the selected parent and removes catch-all choices', async () => {
    await mount()
    expect(api.getDistinctValues).toHaveBeenCalledOnce()
    const options = await openDropdown(dropdown('Categoria'))
    expect(options.map(o => o.value)).toEqual(['CALÇADOS', 'Camisas Sociais', 'Camisetas', 'Coleção Especial'])
    expect(options.some(o => ['Outros', 'Outra', '_custom'].includes(o.value))).toBe(false)
    await chooseDropdown(dropdown('Categoria'), 'Camisetas')
    const children = await openDropdown(dropdown('Subcategoria'))
    expect(children.map(o => [o.value, o.textContent?.trim()])).toEqual([
      ['Manga Longa', 'Camisetas > Manga Longa'], ['Polo', 'Camisetas > Polo'],
    ])
    await chooseDropdown(dropdown('Subcategoria'), 'Polo')
    await chooseDropdown(dropdown('Categoria'), 'CALÇADOS')
    expect(control('Subcategoria').value).toBe('')
    expect((await openDropdown(dropdown('Subcategoria'))).map(o => o.value)).toEqual(['Sociais', 'Tênis>Corrida'])
  })

  it('keeps newly typed multiword text and saves a parent > child path without catch-all sentinels', async () => {
    await mount()
    for (const [label, text] of [['Categoria', 'Roupas de Praia'], ['Subcategoria', 'Saída Longa']]) {
      for (const char of text) await type(label, control(label).value + char)
      expect(control(label).value).toBe(text)
      control(label).dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }))
      await flush()
    }
    await saveNew()
    expect(api.createItem).toHaveBeenCalledWith(expect.objectContaining({ category: 'Roupas de Praia>Saída Longa' }))
    expect(api.updateItem).not.toHaveBeenCalled()
  })

  it('keeps a newly typed substring on Enter instead of replacing it with the first existing category', async () => {
    await mount(); await type('Categoria', 'Camisas')
    control('Categoria').dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }))
    await flush(); expect(control('Categoria').value).toBe('Camisas')
    await saveNew()
    expect(api.createItem).toHaveBeenCalledWith(expect.objectContaining({ category: 'Camisas' }))
  })

  it.each(['Outros', 'Calçados > Tênis > Corrida', 'Coleção Especial>Verão>Praia'])('preserves existing complete paths when editing another field: %s', async category => {
    await mount({ item: { ...item, category } })
    expect(control('Categoria').value).toBe(category.split('>')[0].trim())
    expect(control('Subcategoria').value).toBe(category.split('>').slice(1).map(s => s.trim()).join('>'))
    await click('Atualizar')
    expect(api.updateItem).toHaveBeenCalledWith(item.id, expect.objectContaining({ category }))
  })

  it('retains all category levels when duplicating a product and allows editing its child', async () => {
    await mount({ duplicateContext: { source: item, source_version: 'a'.repeat(64), existing: [], model_name: item.name } })
    expect(control('Categoria').value).toBe('Coleção Especial')
    expect(control('Subcategoria').value).toBe('Verão>Praia')
    await type('Subcategoria', 'Inverno>Montanha'); await saveNew()
    expect(api.duplicate).toHaveBeenCalledWith(item.id, expect.objectContaining({ item: expect.objectContaining({ category: 'Coleção Especial>Inverno>Montanha' }) }))
  })

  it('hydrates a custom hierarchy from a photo suggestion without resetting or truncating it', async () => {
    await mount(); await click('1 · Foto e etiqueta'); await click('Adicionar foto'); await click('Apply photo fixture'); await click('Conferir dados')
    expect(control('Categoria').value).toBe('Coleção Especial')
    expect(control('Subcategoria').value).toBe('Verão>Praia')
    await saveNew()
    expect(api.createItem).toHaveBeenCalledWith(expect.objectContaining({ category: 'Coleção Especial>Verão>Praia' }))
  })

  it('allows typing after a directory failure, retries and never overwrites text with late options', async () => {
    api.getDistinctValues.mockRejectedValueOnce(new Error('offline'))
    await mount(); expect(root.textContent).toContain('Não foi possível carregar as categorias.')
    await type('Categoria', 'Categoria Nova'); await type('Subcategoria', 'Filha Nova')
    await click('Tentar novamente')
    expect(api.getDistinctValues).toHaveBeenCalledTimes(2)
    expect(control('Categoria').value).toBe('Categoria Nova'); expect(control('Subcategoria').value).toBe('Filha Nova')
    expect(root.textContent).not.toContain('Não foi possível carregar as categorias.')
    await saveNew()
    expect(api.createItem).toHaveBeenCalledWith(expect.objectContaining({ category: 'Categoria Nova>Filha Nova' }))
  })

  it('keeps catalog labels untranslated and removes the old grade hint', async () => {
    const i18n = await mount()
    i18n.global.locale.value = 'en'; await flush()
    expect((await openDropdown(dropdown('Category'))).map(o => o.value)).toContain('Coleção Especial')
    i18n.global.locale.value = 'pt'; await flush()
    await saveNew()
    await click('Criar grade deste modelo')
    expect(root.textContent).not.toContain('Escolha um modelo de tamanhos.')
  })
})
