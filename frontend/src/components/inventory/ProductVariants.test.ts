import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import ProductVariantsModal from './ProductVariantsModal.vue'

const api = vi.hoisted(() => ({ context: vi.fn(), create: vi.fn() }))
vi.mock('@/services/inventoryVariants', () => ({ inventoryVariantsAPI: api }))
let app: App, root: HTMLDivElement
const saved = vi.fn()
const fixture = () => ({ source: { id: 'source', name: 'Tênis 9', size: '9', color: 'Branco', barcode: '1239', image_data: 'data:image/png;base64,fixture' }, source_version: 'a'.repeat(64), model_name: 'Tênis', existing: [{ id: 'source', size: '9' }] })
const flush = async () => { await nextTick(); await Promise.resolve(); await nextTick() }
async function mount(mode: 'duplicate' | 'grade' = 'duplicate') {
  root = document.createElement('div'); document.body.append(root)
  app = createApp(ProductVariantsModal, { itemId: 'source', mode, onSaved: saved }).use(createI18n({ legacy: false, locale: 'pt', messages: { pt: {} } }))
  app.directive('erp-dialog', {}); app.mount(root); await flush()
}
async function field(label: string, value: string) {
  const input = Array.from(root.querySelectorAll('label')).find(l => l.textContent?.trim() === label)?.querySelector('input') as HTMLInputElement
  expect(input).toBeTruthy(); input.value = value; input.dispatchEvent(new Event('input', { bubbles: true })); await flush()
}
async function confirm() { const input = root.querySelector('[type=checkbox]') as HTMLInputElement; input.checked = true; input.dispatchEvent(new Event('change', { bubbles: true })); await flush() }
async function submit() { root.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await flush() }
beforeEach(() => { localStorage.clear(); api.context.mockResolvedValue(fixture()); api.create.mockResolvedValue({ created: [{ id: 'new', size: '8' }], existing: [], group_key: 'group' }) })
afterEach(() => { app?.unmount(); root?.remove(); vi.resetAllMocks() })

describe('Existing product variants', () => {
  it('reuses source photo and creates a reviewed size without copying source stock or identity', async () => {
    await mount(); expect(root.querySelector('img')?.src).toContain('base64,fixture')
    await field('Novo tamanho', '8'); await submit(); expect(api.create).not.toHaveBeenCalled()
    await field('Código base (opcional)', '123'); await field('Quantidade por novo tamanho', '2'); await confirm(); await submit()
    expect(api.create).toHaveBeenCalledWith('source', { sizes: ['8'], model_name: 'Tênis', base_barcode: '123', source_version: 'a'.repeat(64), initial_stock: 2, stock_location: 'loja', confirm: true })
    expect(saved).toHaveBeenCalledOnce()
  })
  it('shows existing sizes as preserved and blocks creating only an existing size', async () => {
    await mount(); await field('Novo tamanho', '9'); await confirm(); await submit()
    expect(root.textContent).toContain('Já cadastrado: estoque preservado'); expect(api.create).not.toHaveBeenCalled()
    await field('Novo tamanho', '8.5'); expect((root.querySelector('[type=checkbox]') as HTMLInputElement).checked).toBe(false)
    await confirm(); await submit(); expect(api.create.mock.calls[0][1].sizes).toEqual(['8.5'])
  })
  it('supports multiple sizes and skips defaults hidden by the option editor', async () => {
    localStorage.setItem('inv_grade_hidden_presets', JSON.stringify(['p → 2xl']))
    await mount('grade'); expect(root.textContent).not.toContain('P → 2XL')
    await field('Tamanhos da grade', '8; 9; 10; 8'); await confirm(); await submit()
    expect(api.create.mock.calls[0][1].sizes).toEqual(['8', '9', '10'])
    expect(api.create.mock.calls[0][1].initial_stock).toBe(0)
  })
  it('requires a fresh lookup after uncertain responses and prevents duplicate stock on retry', async () => {
    api.create.mockRejectedValueOnce(new Error('network failure'))
    await mount(); await field('Novo tamanho', '8'); await confirm(); await submit()
    expect(root.querySelector('fieldset')?.disabled).toBe(true)
    await submit(); expect(api.create).toHaveBeenCalledTimes(1)
    api.context.mockResolvedValueOnce({ ...fixture(), existing: [{ id: 'new', size: '8' }] })
    const button = Array.from(root.querySelectorAll('button')).find(b => b.textContent === 'Conferir tamanhos cadastrados')!
    button.click(); await flush(); await confirm(); await submit()
    expect(api.create).toHaveBeenCalledTimes(1); expect(root.textContent).toContain('Novos tamanhos: 0')
  })
})
