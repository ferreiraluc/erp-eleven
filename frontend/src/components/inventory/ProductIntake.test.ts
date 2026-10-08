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
async function mount(onClose = () => {}) {
  root = document.createElement('div'); document.body.append(root)
  const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp(ItemFormModal, { onClose }).use(i18n); app.mount(root); await nextTick()
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
afterEach(() => { app?.unmount(); root?.remove(); vi.restoreAllMocks(); vi.resetAllMocks() })

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
    await click('3 · Estoque'); expect(root.querySelector('.intake-review-check')).not.toBeNull(); expect(root.textContent).toContain('Confira os dados e resolva as diferenças')
  })
  it('allows manual-only registration and refuses to skip review', async () => {
    await mount(); await click('3 · Estoque'); expect(root.querySelector('.intake-review-check')).not.toBeNull(); expect(root.textContent).toContain('Confira os dados e resolva as diferenças')
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

it('makes review visible in the footer and returns to it when stock is requested directly', async () => {
  await mount(); await click('3 · Estoque')
  expect(root.querySelector('.modal-footer .intake-review-check')).not.toBeNull()
  expect(root.querySelector('.intake-stock-summary')).toBeNull()
  await setField('Nome *', 'Grade teste'); await review(); await click('Criar grade deste modelo')
  await click('Criar')
  expect(mock.createItem).not.toHaveBeenCalled()
  expect(root.querySelector('.submit-error')?.textContent).toContain('Selecione um modelo')
  await click('P → 2XL'); await click('Criar grade (5 itens)')
  expect(mock.createGrade).toHaveBeenCalledOnce()
})

describe('Reusable grade and color editors', () => {
  async function openGrade() { await click('Conferir dados'); await setField('Nome *', 'Produto de teste'); await review(); await click('Criar grade deste modelo') }
  async function select(selector: string) {
    const el = root.querySelector<HTMLButtonElement>(selector)
    if (!el) throw Error(`Missing control: ${selector}`)
    el.click(); await nextTick(); await nextTick()
  }
  async function type(selector: string, text: string) {
    const el = root.querySelector<HTMLInputElement>(selector)!
    el.value = text; el.dispatchEvent(new Event('input', { bubbles: true })); await nextTick()
    return el
  }
  async function preset(name = 'M ao 3XL', sizes = 'M, L, XL, 2XL, 3XL') {
    await select('[aria-label="Novo modelo de grade"]')
    await type('.new-preset-form input', name)
    return type('.new-preset-form input[placeholder="M, L, XL, 2XL, 3XL"]', sizes)
  }
  async function color(text: string) {
    await select('button[aria-label="Adicionar cor"]')
    return type('input[aria-label="Adicionar cor"]', text)
  }
  function noInventoryWrites() {
    expect(mock.createItem).not.toHaveBeenCalled()
    expect(mock.createGrade).not.toHaveBeenCalled()
    expect(mock.createMovement).not.toHaveBeenCalled()
  }
  it('saves all typed sizes by clicking, without confirming each one, and reuses the preset after reopening', async () => {
    await mount(); await openGrade(); await preset('M ao 3XL', 'm, l XL; 2XL 3XL m')
    expect(button('Adicionar modelo').disabled).toBe(false)
    expect(root.querySelectorAll('.preset-size-preview .grade-chip')).toHaveLength(5)
    await click('Adicionar modelo')
    expect(root.querySelector('.new-preset-form')).toBeNull()
    expect(button('M ao 3XL').getAttribute('aria-pressed')).toBe('true')
    expect(JSON.parse(localStorage.getItem('inv_grade_custom_presets')!)[0].sizes).toEqual(['M', 'L', 'XL', '2XL', '3XL'])
    expect(document.activeElement).toBe(root.querySelector('[aria-label="Novo modelo de grade"]'))
    app.unmount(); root.remove(); await mount(); await openGrade(); await click('M ao 3XL')
    expect(button('Criar grade (5 itens)')).toBeDefined(); noInventoryWrites()
  })
  it('saves a preset with Enter and rejects duplicate names without overwriting saved sizes', async () => {
    await mount(); await openGrade()
    const el = await preset()
    el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })); await nextTick()
    expect(button('M ao 3XL')).toBeDefined()
    await preset('  m AO 3XL  ', 'M L'); await click('Adicionar modelo')
    expect(root.textContent).toContain('Já existe um modelo com esse nome.')
    expect(JSON.parse(localStorage.getItem('inv_grade_custom_presets')!)).toHaveLength(1)
    expect(JSON.parse(localStorage.getItem('inv_grade_custom_presets')!)[0].sizes).toHaveLength(5)
    noInventoryWrites()
  })
  it('adds a color with the visible button after blur, saves its option and preserves it when deselected', async () => {
    await mount(); await openGrade()
    const el = await color('  azul   MARINHO  ')
    el.dispatchEvent(new Event('blur')); await nextTick(); await click('Adicionar')
    expect(root.querySelector('.quick-color-entry')).toBeNull()
    expect(root.querySelectorAll('.quick-colors button.active')).toHaveLength(1)
    expect(root.querySelector('.selected-colors')?.textContent).toContain('Azul Marinho')
    await select('.selected-colors button')
    expect(button('Azul Marinho').getAttribute('aria-pressed')).toBe('false')
    app.unmount(); root.remove(); await mount(); await openGrade(); await click('Azul Marinho')
    expect(root.querySelector('.selected-colors')?.textContent).toContain('Azul Marinho')
    expect(JSON.parse(localStorage.getItem('inv_grade_custom_colors')!)).toEqual(['Azul Marinho'])
    noInventoryWrites()
  })
  it('adds colors with Enter and reuses existing/default colors without duplicate buttons', async () => {
    await mount(); await openGrade()
    for (const text of ['Lilás', ' lilás ', 'preto']) {
      const el = await color(text)
      el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })); await nextTick()
    }
    expect(JSON.parse(localStorage.getItem('inv_grade_custom_colors')!)).toEqual(['Lilás'])
    expect(root.querySelectorAll('.quick-colors button.active')).toHaveLength(2)
    expect(root.querySelectorAll('.selected-colors .grade-chip')).toHaveLength(2)
    noInventoryWrites()
  })
  it('cancels each editor with Escape without closing the product or saving a draft', async () => {
    const close = vi.fn(); await mount(close); await openGrade()
    const sizeInput = await preset()
    sizeInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })); await nextTick()
    expect(root.querySelector('.new-preset-form')).toBeNull()
    const colorInput = await color('Roxo')
    colorInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })); await nextTick()
    expect(root.querySelector('.quick-color-entry')).toBeNull()
    expect(document.activeElement).toBe(root.querySelector('button[aria-label="Adicionar cor"]'))
    expect(close).not.toHaveBeenCalled()
    expect(localStorage.getItem('inv_grade_custom_presets')).toBeNull()
    expect(localStorage.getItem('inv_grade_custom_colors')).toBeNull(); noInventoryWrites()
  })
  it('recovers from malformed local options and keeps existing valid presets', async () => {
    localStorage.setItem('inv_grade_custom_presets', JSON.stringify([null, { label: 'broken' }, { label: 'Antigo', sizes: ['p', 'M'] }]))
    localStorage.setItem('inv_grade_custom_colors', '{invalid')
    await mount(); await openGrade(); await click('Antigo')
    expect(button('Criar grade (2 itens)')).toBeDefined()
    await color('Lilás'); await click('Adicionar')
    expect(JSON.parse(localStorage.getItem('inv_grade_custom_colors')!)).toEqual(['Lilás']); noInventoryWrites()
  })
  it('keeps both editors and their text on storage failure, allowing retry without false success', async () => {
    await mount(); await openGrade(); await preset()
    const save = vi.spyOn(localStorage, 'setItem').mockImplementation(() => { throw new DOMException('Full', 'QuotaExceededError') })
    await click('Adicionar modelo')
    expect(root.querySelector<HTMLInputElement>('.new-preset-form input')?.value).toBe('M ao 3XL')
    expect(root.textContent).toContain('Não foi possível salvar neste navegador.')
    expect(root.querySelectorAll('.preset-option')).toHaveLength(5)
    await color('Lilás'); await click('Adicionar')
    expect(root.querySelector<HTMLInputElement>('input[aria-label="Adicionar cor"]')?.value).toBe('Lilás')
    expect(root.querySelector('.selected-colors')).toBeNull()
    save.mockRestore(); await click('Adicionar'); await click('Adicionar modelo')
    expect(localStorage.getItem('inv_grade_custom_colors')).toContain('Lilás')
    expect(button('M ao 3XL')).toBeDefined(); noInventoryWrites()
  })
  it('removes a saved color and its selection, preserves sizes, and allows adding it again later', async () => {
    localStorage.setItem('inv_grade_custom_colors', JSON.stringify(['M', 'Lilás']))
    await mount(); await openGrade(); await click('P → 2XL'); await click('M')
    expect(root.querySelector('[aria-label="Remover cor M"]')).toBeNull()
    await click('Editar opções'); await select('[aria-label="Remover cor M"]')
    expect(root.querySelector('[aria-label="Remover cor M"]')).toBeNull()
    expect(root.querySelector('.selected-colors')).toBeNull()
    expect(root.querySelector('.grade-chips')?.textContent).toContain('M')
    expect(root.textContent).toContain('Cor M removida dos botões salvos.')
    expect(JSON.parse(localStorage.getItem('inv_grade_custom_colors')!)).toEqual(['Lilás'])
    expect(document.activeElement).toBe(root.querySelector('button[aria-label="Adicionar cor"]'))
    await click('Concluir edição')
    expect(root.querySelector('[aria-label="Remover cor Lilás"]')).toBeNull()
    app.unmount(); root.remove(); await mount(); await openGrade()
    expect(Array.from(root.querySelectorAll('.quick-colors button')).some(b => b.textContent?.trim() === 'M')).toBe(false)
    await color('M'); await click('Adicionar')
    expect(JSON.parse(localStorage.getItem('inv_grade_custom_colors')!)).toEqual(['Lilás', 'M'])
    noInventoryWrites()
  })
  it('removes a custom preset without erasing the current size draft or built-in options', async () => {
    await mount(); await openGrade(); await preset(); await click('Adicionar modelo')
    await click('Editar opções')
    expect(root.querySelector('[aria-label="Remover modelo P → 2XL"]')).not.toBeNull()
    expect(root.querySelector('[aria-label="Remover cor Preto"]')).not.toBeNull()
    await select('[aria-label="Remover modelo M ao 3XL"]')
    expect(root.textContent).toContain('Modelo M ao 3XL removido dos botões salvos.')
    expect(button('Criar grade (5 itens)')).toBeDefined()
    expect(JSON.parse(localStorage.getItem('inv_grade_custom_presets')!)).toEqual([])
    app.unmount(); root.remove(); await mount(); await openGrade()
    expect(Array.from(root.querySelectorAll('.grade-presets button')).some(b => b.textContent?.trim() === 'M ao 3XL')).toBe(false)
    expect(button('P → 2XL')).toBeDefined(); noInventoryWrites()
  })
  it('does not remove saved options or selected colors when storage fails', async () => {
    localStorage.setItem('inv_grade_custom_colors', JSON.stringify(['M']))
    await mount(); await openGrade(); await preset(); await click('Adicionar modelo'); await click('M')
    await click('Editar opções')
    const save = vi.spyOn(localStorage, 'setItem').mockImplementation(() => { throw Error('Storage unavailable') })
    await select('[aria-label="Remover cor M"]'); await select('[aria-label="Remover modelo M ao 3XL"]')
    expect(root.querySelector('.selected-colors')?.textContent).toContain('M')
    expect(button('M ao 3XL')).toBeDefined()
    expect(root.textContent).toContain('Não foi possível salvar neste navegador.')
    expect(root.textContent).not.toContain('removida dos botões salvos.')
    expect(localStorage.getItem('inv_grade_custom_colors')).toBe('["M"]')
    save.mockRestore(); await select('[aria-label="Remover cor M"]'); await select('[aria-label="Remover modelo M ao 3XL"]')
    expect(localStorage.getItem('inv_grade_custom_colors')).toBe('[]')
    expect(localStorage.getItem('inv_grade_custom_presets')).toBe('[]'); noInventoryWrites()
  })
  it('removes built-in colors and presets persistently, keeping unrelated custom options and current sizes', async () => {
    localStorage.setItem('inv_grade_custom_colors', '["Lilás"]')
    await mount(); await openGrade(); await click('P → 2XL'); await click('Preto'); await click('Editar opções')
    await select('[aria-label="Remover cor Preto"]'); await select('[aria-label="Remover modelo P → 2XL"]')
    expect(root.querySelector('.selected-colors')).toBeNull()
    expect(button('Criar grade (5 itens)')).toBeDefined()
    expect(button('Lilás')).toBeDefined()
    app.unmount(); root.remove(); await mount(); await openGrade()
    expect(Array.from(root.querySelectorAll('.quick-colors button')).some(b => b.textContent?.trim() === 'Preto')).toBe(false)
    expect(Array.from(root.querySelectorAll('.grade-presets button')).some(b => b.textContent?.trim() === 'P → 2XL')).toBe(false)
    expect(button('Lilás')).toBeDefined(); expect(button('46 → 54')).toBeDefined(); noInventoryWrites()
  })
  it('allows re-adding removed defaults without duplicate buttons or losing the new sizes on reopen', async () => {
    await mount(); await openGrade(); await click('Editar opções')
    await select('[aria-label="Remover cor Preto"]'); await select('[aria-label="Remover modelo P → 2XL"]')
    await color('preto'); await click('Adicionar'); await preset('P → 2XL', 'P M'); await click('Adicionar modelo')
    app.unmount(); root.remove(); await mount(); await openGrade()
    expect(Array.from(root.querySelectorAll('.quick-colors button')).filter(b => b.textContent?.trim() === 'Preto')).toHaveLength(1)
    expect(Array.from(root.querySelectorAll('.grade-presets button')).filter(b => b.textContent?.trim() === 'P → 2XL')).toHaveLength(1)
    await click('P → 2XL'); expect(button('Criar grade (2 itens)')).toBeDefined()
    await click('Editar opções'); await select('[aria-label="Remover modelo P → 2XL"]')
    app.unmount(); root.remove(); await mount(); await openGrade()
    expect(Array.from(root.querySelectorAll('.grade-presets button')).some(b => b.textContent?.trim() === 'P → 2XL')).toBe(false)
    noInventoryWrites()
  })
  it('preserves built-in buttons and selections if saving their removal fails', async () => {
    await mount(); await openGrade(); await click('Preto'); await click('P → 2XL'); await click('Editar opções')
    vi.spyOn(localStorage, 'setItem').mockImplementation(() => { throw Error('Storage unavailable') })
    await select('[aria-label="Remover cor Preto"]'); await select('[aria-label="Remover modelo P → 2XL"]')
    expect(root.querySelector('.selected-colors')?.textContent).toContain('Preto')
    expect(button('P → 2XL').getAttribute('aria-pressed')).toBe('true')
    expect(root.textContent).toContain('Não foi possível salvar neste navegador.')
    expect(localStorage.getItem('inv_grade_hidden_colors')).toBeNull()
    expect(localStorage.getItem('inv_grade_hidden_presets')).toBeNull(); noInventoryWrites()
  })
})
