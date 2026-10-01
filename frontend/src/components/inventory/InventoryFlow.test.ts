import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, type App, type Component } from 'vue'
import { createI18n } from 'vue-i18n'
import MovementModal from './MovementModal.vue'
import ItemFormModal from './ItemFormModal.vue'
import BulkTransferModal from './BulkTransferModal.vue'
import { inventoryMessages, useInventoryI18n } from './i18n'

const api = vi.hoisted(() => ({ createMovement: vi.fn(), createBatchMovement: vi.fn(), transferBulk: vi.fn(),
  createItem: vi.fn(), updateItem: vi.fn(), createGrade: vi.fn(), getByBarcode: vi.fn() }))
vi.mock('@/services/api', () => ({ inventoryAPI: api, ocrAPI: {} }))
let app: App | undefined, container: HTMLDivElement
const item = { id: 'item-1', name: 'Loja', sku_internal: 'TEST-001', current_stock: 10, stock_loja: 5, stock_deposito: 5,
  cost_price: 0, sale_price: 0, currency: 'PYG', is_active: true }
async function mount(component: Component, props: Record<string, unknown> = {}) {
  container = document.createElement('div'); document.body.append(container)
  const i18n = createI18n({ legacy: false, locale: 'pt', fallbackLocale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp(component, props).use(i18n); app.mount(container); await nextTick()
  return i18n
}
function button(text: string) {
  const found = Array.from(container.querySelectorAll('button')).find(b => b.textContent?.trim() === text)
  if (!found) throw new Error(`Button missing: ${text}`)
  return found
}
function setInput(input: HTMLInputElement, value: string) {
  input.value = value; input.dispatchEvent(new Event('input', { bubbles: true }))
}
function field(label: string) {
  const group = Array.from(container.querySelectorAll('.form-group')).find(g => g.querySelector('label')?.textContent?.trim() === label)
  if (!group) throw new Error(`Field missing: ${label}`)
  return group.querySelector('input') as HTMLInputElement
}
beforeEach(() => {
  localStorage.clear(); api.createMovement.mockResolvedValue({}); api.transferBulk.mockResolvedValue({})
  api.createItem.mockResolvedValue(item); api.getByBarcode.mockResolvedValue([])
})
afterEach(() => { app?.unmount(); container?.remove(); vi.resetAllMocks() })

describe('Inventory locale and movement contracts', () => {
  it('translates an open movement modal and validation while retaining adjustment/location values', async () => {
    const i18n = await mount(MovementModal, { item })
    i18n.global.locale.value = 'es'; await nextTick()
    expect(container.textContent).toContain('Movimiento de stock')
    expect(container.querySelector('.item-name')?.textContent).toBe('Loja')
    i18n.global.locale.value = 'en'; await nextTick()
    expect(container.textContent).toContain('Stock movement')
    button('Adjustment').click(); await nextTick()
    button('Warehouse').click(); await nextTick()
    setInput(field('Quantity *'), '0')
    button('Register').click(); await nextTick()
    expect(api.createMovement).not.toHaveBeenCalled()
    expect(container.textContent).toContain('A reason is required for adjustments')
    i18n.global.locale.value = 'es'; await nextTick()
    expect(container.textContent).toContain('Se requiere motivo para el ajuste')
    setInput(container.querySelector('input[placeholder="Motivo del movimiento..."]') as HTMLInputElement, 'Contagem local')
    button('Registrar').click(); await nextTick()
    expect(api.createMovement).toHaveBeenCalledWith(expect.objectContaining({ movement_type: 'adjustment', quantity: 0, location: 'deposito', reason: 'Contagem local' }))
  })

  it('changes transfer labels without translating operational names or direction payload', async () => {
    const i18n = await mount(BulkTransferModal, { items: [item] })
    i18n.global.locale.value = 'en'; await nextTick()
    expect(container.textContent).toContain('Selected items: 1')
    expect(container.textContent).toContain('Units to transfer: 1')
    expect(container.querySelector('.row-name')?.textContent).toBe('Loja')
    button('Transfer').click(); await nextTick()
    expect(api.transferBulk).toHaveBeenCalledWith(expect.objectContaining({ direction: 'deposito_to_loja', items: [{ item_id: 'item-1', quantity: 1 }] }))
  })

  it('preserves interpolation keys in all translations and formats numbers with reactive locale', async () => {
    const tokens = (value: string) => [...value.matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort()
    for (const [source, languages] of Object.entries(inventoryMessages)) {
      expect(languages).toHaveLength(2)
      for (const translated of languages) {
        expect(translated.trim()).not.toBe('')
        expect(tokens(translated), source).toEqual(tokens(source))
      }
    }
    const Harness = defineComponent({ setup() { const { tr, numberLocale } = useInventoryI18n()
      return () => h('p', `${tr('Já pertence ao grupo: {group}', { group: 'Loja' })} / ${Number(1234.5).toLocaleString(numberLocale())} / ${tr('Saldo insuficiente no local de origem: disponível 2, solicitado 8.')}`)
    } })
    const i18n = await mount(Harness)
    expect(container.textContent).toContain('1.234,5')
    i18n.global.locale.value = 'en'; await nextTick()
    expect(container.textContent).toContain('Already belongs to group: Loja / 1,234.5')
    expect(container.textContent).toContain('Insufficient source stock: available 2, requested 8.')
    i18n.global.locale.value = 'es'; await nextTick()
    expect(container.textContent).toContain('Ya pertenece al grupo: Loja')
  })
})

describe('Initial stock registration failures', () => {
  it('rejects a fractional initial balance before creating any item', async () => {
    await mount(ItemFormModal)
    setInput(container.querySelector('input[placeholder="Nome do produto"]') as HTMLInputElement, 'Loja')
    button('Estoque').click(); await nextTick()
    setInput(field('Estoque inicial'), '1.5')
    button('Criar').click(); await nextTick()
    expect(api.createItem).not.toHaveBeenCalled()
    expect(api.createMovement).not.toHaveBeenCalled()
    expect(container.textContent).toContain('Estoque inicial deve ser inteiro')
  })

  it('reports an item already created when initial stock fails and prevents a duplicate retry', async () => {
    api.createMovement.mockRejectedValue({ response: { status: 409, data: { detail: 'O saldo por local diverge do total ou está negativo. Confira o inventário e registre um ajuste antes de movimentar.' } } })
    const saved = vi.fn(), partial = vi.fn()
    const i18n = await mount(ItemFormModal, { onSaved: saved, onPartial: partial })
    setInput(container.querySelector('input[placeholder="Nome do produto"]') as HTMLInputElement, 'Loja')
    button('Estoque').click(); await nextTick()
    setInput(field('Estoque inicial'), '5')
    button('Criar').click()
    await vi.waitFor(() => expect(partial).toHaveBeenCalledWith([item]))
    expect(saved).not.toHaveBeenCalled()
    expect(api.createItem).toHaveBeenCalledTimes(1)
    expect(api.createMovement).toHaveBeenCalledTimes(1)
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('Cadastro parcialmente concluído')
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('TEST-001')
    expect(Array.from(container.querySelectorAll('.modal-footer button')).map(b => b.textContent?.trim())).toEqual(['Fechar'])
    i18n.global.locale.value = 'en'; await nextTick()
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('Registration partially completed')
    expect(api.createItem).toHaveBeenCalledTimes(1)
  })

  it('keeps a normal successful creation flow with exactly one initial movement', async () => {
    const saved = vi.fn(), partial = vi.fn()
    await mount(ItemFormModal, { onSaved: saved, onPartial: partial })
    setInput(container.querySelector('input[placeholder="Nome do produto"]') as HTMLInputElement, 'Loja')
    button('Estoque').click(); await nextTick()
    setInput(field('Estoque inicial'), '3')
    button('Criar').click()
    await vi.waitFor(() => expect(saved).toHaveBeenCalledWith(item))
    expect(partial).not.toHaveBeenCalled()
    expect(api.createMovement).toHaveBeenCalledWith(expect.objectContaining({ item_id: 'item-1', quantity: 3, location: 'loja' }))
  })

  it('retains the already created color when a later variant fails', async () => {
    api.createItem.mockReset().mockResolvedValueOnce(item).mockRejectedValueOnce({ response: { status: 409, data: { detail: 'Erro ao salvar' } } })
    const saved = vi.fn(), partial = vi.fn()
    await mount(ItemFormModal, { onSaved: saved, onPartial: partial })
    setInput(container.querySelector('input[placeholder="Nome do produto"]') as HTMLInputElement, 'Loja')
    button('Grade').click(); await nextTick()
    button('Navy').click(); button('Branco').click(); await nextTick()
    setInput(field('Estoque inicial por tamanho'), '2')
    button('Criar grade (2 itens)').click()
    await vi.waitFor(() => expect(partial).toHaveBeenCalledWith([item]))
    expect(saved).not.toHaveBeenCalled()
    expect(api.createItem).toHaveBeenCalledTimes(2)
    expect(api.createMovement).toHaveBeenCalledTimes(1)
    expect(api.createItem.mock.calls.map(call => call[0].color)).toEqual(['Navy', 'Branco'])
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('Itens já criados: 1')
    expect(Array.from(container.querySelectorAll('.modal-footer button')).map(b => b.textContent?.trim())).toEqual(['Fechar'])
  })

  it('blocks uncertain network retries until the user checks inventory', async () => {
    api.createItem.mockRejectedValue(new Error('Network timeout'))
    const saved = vi.fn(), partial = vi.fn()
    await mount(ItemFormModal, { onSaved: saved, onPartial: partial })
    setInput(container.querySelector('input[placeholder="Nome do produto"]') as HTMLInputElement, 'Loja')
    button('Criar').click()
    await vi.waitFor(() => expect(partial).toHaveBeenCalledWith([]))
    expect(saved).not.toHaveBeenCalled(); expect(api.createMovement).not.toHaveBeenCalled()
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('Confira o inventário antes de tentar criar novamente.')
    expect(Array.from(container.querySelectorAll('.modal-footer button')).map(b => b.textContent?.trim())).toEqual(['Fechar'])
  })
})
