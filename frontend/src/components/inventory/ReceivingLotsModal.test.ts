import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import ReceivingLotsModal from './ReceivingLotsModal.vue'
const api = vi.hoisted(() => ({
  list: vi.fn(),
  candidates: vi.fn(),
  create: vi.fn(),
  edit: vi.fn(),
  members: vi.fn(),
  attach: vi.fn(),
  detach: vi.fn(),
}))
vi.mock('@/services/inventoryReceiving', () => ({ receivingAPI: api }))
const lot = {
  id: 'lot',
  name: 'Leva 1',
  notes: 'Container',
  received_on: '2026-10-15',
  item_count: 2,
}
let app: App, root: HTMLDivElement
const flush = async () => {
  await nextTick()
  await Promise.resolve()
  await nextTick()
}
async function mount(selection: object[] = []) {
  root = document.createElement('div')
  document.body.append(root)
  app = createApp(ReceivingLotsModal, { selection, canManage: true }).use(
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
async function set(label: string, value: string) {
  const el = Array.from(root.querySelectorAll('label'))
    .find((l) => l.textContent?.trim() === label)
    ?.querySelector('input') as HTMLInputElement
  expect(el, label).toBeTruthy()
  el.value = value
  el.dispatchEvent(new Event('input', { bubbles: true }))
  await flush()
}
async function confirm() {
  const input = root.querySelector<HTMLInputElement>('.receiving-confirm input')!
  input.checked = true
  input.dispatchEvent(new Event('change', { bubbles: true }))
  await flush()
}
beforeEach(() => {
  api.list.mockResolvedValue({ items: [lot], total: 1 })
  api.candidates.mockResolvedValue({
    items: [
      { id: 'a', name: 'Camiseta A' },
      { id: 'b', name: 'Camiseta B' },
    ],
    total: 2,
  })
  api.create.mockResolvedValue(lot)
  api.members.mockResolvedValue({ lot, items: [] })
  api.attach.mockResolvedValue(lot)
})
afterEach(() => {
  app?.unmount()
  root?.remove()
  vi.resetAllMocks()
})
it('previews all date results and freezes only the reviewed selected identities', async () => {
  await mount()
  await click('+ Novo lote')
  await set('Nome do lote', 'Chegada 15')
  await set('Cadastro de', '2026-10-15')
  await set('Até', '2026-10-15')
  await click('Buscar produtos')
  expect(api.candidates).toHaveBeenCalledWith('2026-10-15', '2026-10-15')
  const input = root.querySelector<HTMLInputElement>('.receiving-product input')!
  input.checked = false
  input.dispatchEvent(new Event('change', { bubbles: true }))
  await flush()
  await confirm()
  await click('Criar lote')
  expect(api.create).toHaveBeenCalledWith(
    expect.objectContaining({ name: 'Chegada 15', item_ids: ['b'], confirm: true }),
  )
  expect(api.attach).not.toHaveBeenCalled()
})
it('clears stale date selections and invalidates review before another period is saved', async () => {
  await mount()
  await click('+ Novo lote')
  await set('Nome do lote', 'Chegada')
  await set('Cadastro de', '2026-10-15')
  await set('Até', '2026-10-15')
  await click('Buscar produtos')
  await confirm()
  await set('Até', '2026-10-17')
  await click('Criar lote')
  expect(api.create).not.toHaveBeenCalled()
  expect(root.querySelectorAll('.receiving-product')).toHaveLength(0)
})
it('attaches manual selections to an existing lot, without creating products or a second lot', async () => {
  await mount([{ id: 'manual', name: 'Escolhido no estoque' }])
  await click('Vincular seleção')
  expect(root.textContent).toContain('Escolhido no estoque')
  await confirm()
  await click('Vincular produtos')
  expect(api.attach).toHaveBeenCalledWith('lot', ['manual'])
  expect(api.create).not.toHaveBeenCalled()
})
it('reuses the exact request identity and blocks edits when the result is uncertain', async () => {
  api.create.mockRejectedValueOnce(new Error('network'))
  await mount()
  await click('+ Novo lote')
  await set('Nome do lote', 'Chegada')
  await click('Buscar produtos')
  await confirm()
  await click('Criar lote')
  const first = JSON.stringify(api.create.mock.calls[0][0])
  expect(root.querySelector('fieldset')!.disabled).toBe(true)
  await click('Conferir resultado')
  expect(JSON.stringify(api.create.mock.calls[1][0])).toBe(first)
})
