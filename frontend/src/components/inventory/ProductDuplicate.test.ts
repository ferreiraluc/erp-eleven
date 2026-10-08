import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import ItemFormModal from './ItemFormModal.vue'
import type { VariantContext } from '@/services/inventoryVariants'
const mock = vi.hoisted(() => ({ duplicate: vi.fn(), photoSeed: '', updateItem: vi.fn(), createItem: vi.fn(), context: vi.fn() }))
vi.mock('@/services/inventoryVariants', () => ({ inventoryVariantsAPI: { duplicate: mock.duplicate, context: mock.context } }))
vi.mock('@/services/api', () => ({ inventoryAPI: { updateItem: mock.updateItem, createItem: mock.createItem, getByBarcode: vi.fn().mockResolvedValue([]) }, ocrAPI: {} }))
vi.mock('./ProductPhotoAssistant.vue', async () => {
  const { defineComponent, h } = await import('vue')
  return { default: defineComponent({ props: ['open', 'initialImage'], emits: ['result'], setup(props, { emit }) {
    return () => { mock.photoSeed = props.initialImage; return props.open ? h('button', { onClick: () => emit('result', { image_data: 'data:image/png;base64,new' }) }, 'apply edited photo') : null }
  } }) }
})
let app: App, root: HTMLDivElement
const saved = vi.fn()
const source = { id: 'source', name: 'Tênis 9', size: '9', color: 'Branco', brand: 'Marca', category: 'Calçados', image_data: 'data:image/png;base64,original', barcode: '1239', current_stock: 7, stock_loja: 7, stock_deposito: 0, unit: 'par', cost_price: 20, sale_price: 50, cost_currency: 'BRL', sale_currency: 'USD' }
const flush = async () => { await nextTick(); await Promise.resolve(); await nextTick() }
async function mount() {
  root = document.createElement('div'); document.body.append(root)
  app = createApp(ItemFormModal, { duplicateContext: { source, source_version: 'a'.repeat(64), existing: [], model_name: 'Tênis' } as unknown as VariantContext, onSaved: saved }).use(createI18n({ legacy: false, locale: 'pt', messages: { pt: {} } }))
  app.mount(root); await flush()
}
const button = (text: string) => Array.from(root.querySelectorAll('button')).find(b => b.textContent?.trim() === text)!
const field = (label: string) => Array.from(root.querySelectorAll('.form-group')).find(g => g.querySelector('label')?.textContent?.trim() === label)?.querySelector('input') as HTMLInputElement
async function set(label: string, value: string) { const input = field(label); input.value = value; input.dispatchEvent(new Event('input', { bubbles: true })); await flush() }
async function click(text: string) { expect(button(text)).toBeTruthy(); button(text).click(); await flush() }
async function review() { const input = root.querySelector('.intake-review-check input') as HTMLInputElement; input.checked = true; input.dispatchEvent(new Event('change', { bubbles: true })); await flush(); await click('Continuar para estoque') }
beforeEach(() => { mock.duplicate.mockResolvedValue({ ...source, id: 'copy', size: '8' }); localStorage.clear() })
afterEach(() => { app?.unmount(); root?.remove(); vi.resetAllMocks() })
it('changes just the size while preserving copied data and creating a new identity with zero initial stock', async () => {
  await mount(); expect(field('Nome *').value).toBe('Tênis 9'); await set('Tamanho', '8')
  expect(field('Nome *').value).toBe('Tênis 8')
  await review(); await click('Criar')
  const request = mock.duplicate.mock.calls[0][1]
  expect(request.item).toMatchObject({ size: '8', name: 'Tênis 8', unit: 'par', image_data: source.image_data, barcode: source.barcode, cost_price: 20, sale_price: 50 })
  expect(request.item).not.toHaveProperty('id'); expect(request.item).not.toHaveProperty('current_stock')
  expect(request.initial_stock).toBe(0); expect(request.keep_group).toBe(true)
  expect(mock.updateItem).not.toHaveBeenCalled(); expect(mock.createItem).not.toHaveBeenCalled()
})
it('uses the same photo editor, allows different data and an independent model, and requires renewed review', async () => {
  await mount(); await click('Editar foto'); expect(mock.photoSeed).toBe(source.image_data)
  await click('apply edited photo'); await click('Conferir dados')
  await set('Nome *', 'Camisa diferente'); await set('Marca', 'Outra marca'); await set('Cor', 'Azul'); await set('Código de Barras', 'NEW'); await set('Preço de Venda', '99')
  const group = root.querySelector('.duplicate-notice input') as HTMLInputElement; group.checked = false; group.dispatchEvent(new Event('change', { bubbles: true })); await flush()
  await click('Continuar para estoque'); expect(mock.duplicate).not.toHaveBeenCalled()
  await review(); await set('Estoque inicial', '2'); await click('Criar')
  expect(mock.duplicate.mock.calls[0][1]).toMatchObject({ keep_group: false, initial_stock: 2, item: { name: 'Camisa diferente', brand: 'Outra marca', color: 'Azul', barcode: 'NEW', sale_price: 99, image_data: 'data:image/png;base64,new' } })
  expect(source.image_data).toContain('original')
})
it('retries the exact confirmed payload after a lost response instead of creating a second product', async () => {
  mock.duplicate.mockRejectedValueOnce(new Error('lost response'))
  await mount(); await set('Tamanho', '8'); await review(); await click('Criar')
  const first = JSON.stringify(mock.duplicate.mock.calls[0][1]); await set('Nome *', 'Later edit')
  await click('Conferir resultado do cadastro')
  expect(JSON.stringify(mock.duplicate.mock.calls[1][1])).toBe(first); expect(saved).toHaveBeenCalledOnce()
})

it('refreshes an outdated source without discarding edits, and requires review again', async () => {
  mock.duplicate.mockRejectedValueOnce({ response: { status: 409, data: { detail: 'Os dados do produto mudaram.' } } })
  mock.context.mockResolvedValue({ source, source_version: 'b'.repeat(64), existing: [], model_name: 'Tênis' })
  await mount(); await set('Tamanho', '8'); await review(); await click('Criar')
  expect(root.querySelector('.modal-footer [role=alert]')?.textContent).toContain('Os dados do produto mudaram.')
  await set('Nome *', 'Meu tênis corrigido'); await click('Atualizar referência do produto')
  expect(field('Nome *').value).toBe('Meu tênis corrigido')
  expect((root.querySelector('.intake-review-check input') as HTMLInputElement).checked).toBe(false)
  await review(); await click('Criar')
  expect(mock.duplicate.mock.calls[1][1]).toMatchObject({ source_version: 'b'.repeat(64), item: { name: 'Meu tênis corrigido', size: '8' } })
  expect(mock.duplicate.mock.calls[1][1].request_id).not.toBe(mock.duplicate.mock.calls[0][1].request_id)
})
