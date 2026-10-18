import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import BulkEditModal from './BulkEditModal.vue'

const api = vi.hoisted(() => ({ batchEdit: vi.fn() }))
vi.mock('@/services/api', () => ({ inventoryAPI: api }))
let app: App, root: HTMLDivElement
const items = [
  { id: 's-white', name: 'Camiseta S Branca', size: 'S', color: 'Branca' },
  { id: 'm-white', name: 'Camiseta M Branca', size: 'M', color: 'branca' },
  { id: 's-blue', name: 'Camiseta P Azul', size: 'P', color: 'Azul' },
].map(item => ({ ...item, stock_loja: 3, stock_deposito: 2, current_stock: 5, sku_internal: item.id, currency: 'USD', is_active: true }))
const tick = async () => { await nextTick(); await nextTick() }
function button(label: string) {
  const b = Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find(b => b.textContent?.trim() === label)
  if (!b) throw new Error(`Missing button: ${label}`)
  return b
}
async function input(selector: string, value: string) {
  const el = root.querySelector<HTMLInputElement>(selector)!
  el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); await tick()
}
async function choose(label: string, option: string) {
  root.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`)!.click(); await tick()
  button(option).click(); await tick()
}
const quantity = (id: string) => `[data-stock-item="${id}"] input[type=number]`
async function mount(data = items, saved = vi.fn()) {
  root = document.createElement('div'); document.body.append(root)
  const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, en: {}, es: {} } })
  app = createApp(BulkEditModal, { items: data, onSaved: saved }).use(i18n); app.mount(root); await tick()
  return i18n
}
beforeEach(() => { api.batchEdit.mockResolvedValue({}); vi.spyOn(console, 'error').mockImplementation(() => {}) })
afterEach(() => { app?.unmount(); root?.remove(); vi.restoreAllMocks(); vi.resetAllMocks() })

it('applies colors to the selection, allows an individual override and waits for Save', async () => {
  await mount()
  await input('input[aria-label="Cor para vários itens"]', 'Navy')
  button('Aplicar cor a todos').click(); await tick()
  const colorFields = Array.from(root.querySelectorAll('.item-card')).map(card => card.querySelectorAll<HTMLInputElement>('.item-fields input')[1])
  expect(colorFields.map(el => el.value)).toEqual(['Navy', 'Navy', 'Navy'])
  colorFields[1].value = 'Preta'; colorFields[1].dispatchEvent(new Event('input', { bubbles: true })); await tick()
  expect(api.batchEdit).not.toHaveBeenCalled()
  button('Salvar 3 itens').click(); await tick()
  expect(api.batchEdit.mock.calls[0][0]).toMatchObject({ sizes: [
    { id: 's-white', color: 'Navy' }, { id: 'm-white', color: 'Preta' }, { id: 's-blue', color: 'Navy' },
  ], stock_adjustments: [] })
})

it('sets counts by color and canonical size, preserving both locations and individual overrides', async () => {
  await mount()
  await choose('Aplicar quantidade a', 'Cor: branca') // normalized, last display label
  await input('input[aria-label="Quantidade para aplicar"]', '4'); button('Aplicar').click(); await tick()
  expect((root.querySelector(quantity('s-blue')) as HTMLInputElement).value).toBe('3')
  await choose('Aplicar quantidade a', 'Tamanho: S')
  await input('input[aria-label="Quantidade para aplicar"]', '8'); button('Aplicar').click(); await tick()
  await input(quantity('s-blue'), '9')
  await choose('Local do ajuste', 'Depósito')
  await input(quantity('m-white'), '0')
  await choose('Local do ajuste', 'Loja')
  expect((root.querySelector(quantity('s-white')) as HTMLInputElement).value).toBe('8')
  expect(root.querySelector('.stock-summary')?.textContent).toContain('25') // 8+4+9 + 2+0+2
  expect(api.batchEdit).not.toHaveBeenCalled()
  button('Salvar 3 itens').click(); await tick()
  expect(api.batchEdit.mock.calls[0][0].stock_adjustments).toEqual([
    { id: 's-white', stock_loja: 8, stock_deposito: 2, expected_loja: 3, expected_deposito: 2, expected_total: 5 },
    { id: 'm-white', stock_loja: 4, stock_deposito: 0, expected_loja: 3, expected_deposito: 2, expected_total: 5 },
    { id: 's-blue', stock_loja: 9, stock_deposito: 2, expected_loja: 3, expected_deposito: 2, expected_total: 5 },
  ])
})

it('adds/subtracts across a selection atomically and never clips a negative result to zero', async () => {
  await mount()
  await choose('Operação de quantidade', 'Somar ou retirar')
  await input('input[aria-label="Quantidade para aplicar"]', '-4'); button('Aplicar').click(); await tick()
  expect(root.textContent).toContain('Nenhuma linha foi alterada')
  expect(Array.from(root.querySelectorAll<HTMLInputElement>('[data-stock-item] input')).map(i => i.value)).toEqual(['3','3','3'])
  await input('input[aria-label="Quantidade para aplicar"]', '2'); button('Aplicar').click(); await tick()
  expect(Array.from(root.querySelectorAll<HTMLInputElement>('[data-stock-item] input')).map(i => i.value)).toEqual(['5','5','5'])
})

it.each(['', '-1', '1.5', '2147483648'])('blocks invalid final quantity %s without losing the draft', async value => {
  await mount(); await input(quantity('s-white'), value)
  button('Salvar 3 itens').click(); await tick()
  expect(api.batchEdit).not.toHaveBeenCalled()
  expect(root.textContent).toContain('Confira as quantidades')
})

it('preserves known rows when one item is unknown; saves without a reason and shows conflicts', async () => {
  const saved = vi.fn()
  await mount([{ ...items[0], stock_loja: null, current_stock: null } as any, items[1]], saved)
  expect(root.querySelector<HTMLInputElement>(quantity('s-white'))!.disabled).toBe(true)
  await input(quantity('m-white'), '0')
  api.batchEdit.mockRejectedValueOnce({ response: { data: { detail: 'O estoque mudou desde a abertura da edição. Nenhuma alteração foi salva; reabra a edição para conferir os saldos atuais.' } } })
  button('Salvar 2 itens').click(); await tick()
  expect(saved).not.toHaveBeenCalled()
  expect(root.querySelector('.save-error')?.textContent).toContain('O estoque mudou')
  expect(api.batchEdit.mock.calls[0][0].stock_adjustments).toHaveLength(1)
  expect(root.querySelector<HTMLInputElement>(quantity('m-white'))!.value).toBe('0')
})

it('keeps step buttons from focusing inputs and translates controls in an open editor', async () => {
  const i18n = await mount()
  root.querySelector<HTMLButtonElement>('[data-stock-item="s-white"] button[aria-label="Aumentar quantidade"]')!.click(); await tick()
  expect(document.activeElement?.tagName).not.toBe('INPUT')
  expect(root.querySelector<HTMLInputElement>(quantity('s-white'))!.value).toBe('4')
  i18n.global.locale.value = 'es'; await tick()
  expect(root.textContent).toContain('Stock por producto')
  expect(root.textContent).toContain('Motivo del ajuste (opcional)')
})


it('retains the reviewed baseline if the parent refreshes while the editor is open', async () => {
  const rows = reactive([{ ...items[0] }])
  await mount(rows)
  await input(quantity('s-white'), '6')
  rows[0].stock_loja = 7; rows[0].current_stock = 9; await tick()
  button('Salvar 1 itens').click(); await tick()
  expect(api.batchEdit.mock.calls[0][0].stock_adjustments[0]).toMatchObject({
    stock_loja: 6, expected_loja: 3, expected_total: 5,
  })
})
