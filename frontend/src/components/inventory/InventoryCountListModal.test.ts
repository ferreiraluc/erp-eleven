import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import InventoryCountListModal from './InventoryCountListModal.vue'
import { restoreCountListRequest, type CountListPreview, type CountListRequest } from '@/services/inventoryCountList'
import { chooseDropdown } from '@/test/dropdown'

const ids = { user: '10000000-0000-4000-8000-000000000001', a: '20000000-0000-4000-8000-000000000001', b: '20000000-0000-4000-8000-000000000002', hp: '30000000-0000-4000-8000-000000000001', other: '30000000-0000-4000-8000-000000000002' }
const mocks = vi.hoisted(() => ({ preview: vi.fn(), pdf: vi.fn(), print: vi.fn(), job: vi.fn(), jobPdf: vi.fn(), native: false, share: vi.fn(), auth: { user: { id: '' }, token: 'token', userRole: 'ADMIN' } }))
vi.mock('@/services/inventoryCountList', async (original) => ({ ...(await original<typeof import('@/services/inventoryCountList')>()), inventoryCountList: { preview: mocks.preview, pdf: mocks.pdf, print: mocks.print, job: mocks.job, jobPdf: mocks.jobPdf } }))
vi.mock('@/services/nativeFiles', async original => ({ ...await original<typeof import('@/services/nativeFiles')>(), usesNativeFiles: () => mocks.native, shareNativePdf: mocks.share }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))

function preview(): CountListPreview {
  return { snapshot: { version: 1, user_id: ids.user, created_at: '2026-11-02T12:00:00Z', items: [
    { id: ids.a, code: 'INV-A', name: 'Camiseta branca S', color: 'Branco', size: 'S', location: 'Prateleira 1', stock_loja: 2, stock_deposito: 7 },
    { id: ids.b, code: 'INV-B', name: 'Camiseta azul M', color: 'Azul', size: 'M', location: null, stock_loja: null, stock_deposito: -1 },
  ], totals: { items: 2, stock_loja: 2, stock_deposito: 6, unknown_loja: 1, unknown_deposito: 0 } }, signature: 'a'.repeat(64), devices: [{ id: ids.hp, name: 'HP Loja', last_seen_at: '2026-11-02T12:00:00Z' }], suggested_device_id: ids.hp, filename: 'conferencia.pdf' }
}
const printJob = { id: 'job1', status: 'pending', device_id: ids.hp, device_name: 'HP Loja', created_at: '2026-11-02T12:00:00Z', diagnostic_message: null }
const key = `eleven:inventory-count-list:pending:${ids.user}`
let app: App | undefined, root: HTMLDivElement
const onClose = vi.fn()
const clickDownload = vi.fn()
async function flush() { for (let i = 0; i < 12; i++) { await Promise.resolve(); await nextTick() } }
async function mount(selected = [ids.a, ids.b], language = 'pt') {
  root = document.createElement('div'); document.body.append(root)
  app = createApp(InventoryCountListModal, { itemIds: selected, onClose })
    .use(createI18n({ legacy: false, locale: language, messages: { pt: {}, es: {}, en: {} } }))
  app.mount(root); await flush()
}
function button(text: string) {
  const result = Array.from(document.querySelectorAll<HTMLButtonElement>('button')).find(b => b.textContent?.trim() === text)
  if (!result) throw new Error(`Missing button: ${text}`)
  return result
}
async function check() {
  const box = document.querySelector<HTMLInputElement>('.count-confirm input')!
  box.checked = true; box.dispatchEvent(new Event('change', { bubbles: true })); await flush()
}
function unmount() { app?.unmount(); app = undefined; root?.remove() }
function pending(): CountListRequest {
  const p = preview()
  return { snapshot: p.snapshot, signature: p.signature, request_key: '40000000-0000-4000-8000-000000000001', device_id: ids.hp, confirm: true }
}
beforeEach(() => {
  vi.resetAllMocks(); mocks.native = false; localStorage.clear(); sessionStorage.clear()
  mocks.auth = reactive({ user: { id: ids.user }, token: 'token', userRole: 'ADMIN' })
  mocks.preview.mockResolvedValue(preview()); mocks.print.mockResolvedValue(printJob); mocks.job.mockResolvedValue(printJob)
  mocks.pdf.mockResolvedValue(new Blob(['%PDF'], { type: 'application/pdf' })); mocks.jobPdf.mockResolvedValue(new Blob(['%PDF']))
  vi.stubGlobal('URL', { createObjectURL: vi.fn(() => 'blob:test'), revokeObjectURL: vi.fn() })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function(this: HTMLAnchorElement) { clickDownload({ href: this.href, download: this.download }) })
})
afterEach(() => { unmount(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers() })

it('loads every selected ID from the server, separates balances, and never calls a stock mutation', async () => {
  await mount()
  expect(mocks.preview).toHaveBeenCalledWith([ids.a, ids.b])
  expect(document.body.textContent).toContain('2 produtos selecionados')
  expect(document.body.textContent).toContain('Saldos consultados em')
  const rows = document.querySelectorAll('.count-table tbody tr')
  expect(rows).toHaveLength(2)
  expect(rows[1].textContent).toContain('Não informado')
  expect(rows[1].textContent).toContain('-1')
  expect(document.body.textContent).toContain('1 saldos não informados')
  expect(button('Confirmar impressão').disabled).toBe(true)
  expect(mocks.print).not.toHaveBeenCalled()
  button('×').click(); expect(onClose).toHaveBeenCalledOnce()
})

it('requires a printer choice when ambiguous and explicit confirmation before creating one job', async () => {
  const data = preview(); data.devices.push({ id: ids.other, name: 'HP Depósito', last_seen_at: null }); data.suggested_device_id = null
  mocks.preview.mockResolvedValue(data); await mount()
  await check(); expect(button('Confirmar impressão').disabled).toBe(true)
  await chooseDropdown(document.querySelector('#count-list-printer'), ids.hp)
  expect(button('Confirmar impressão').disabled).toBe(true)
  await check()
  mocks.print.mockImplementation(async (request) => {
    expect(JSON.parse(sessionStorage.getItem(key)!)).toEqual(request)
    return printJob
  })
  const print = button('Confirmar impressão'); print.click(); print.click(); await flush()
  expect(mocks.print).toHaveBeenCalledOnce()
  expect(mocks.print.mock.calls[0][0]).toEqual(expect.objectContaining({ snapshot: data.snapshot, signature: data.signature, device_id: ids.hp, confirm: true }))
  expect(sessionStorage.getItem(key)).toBeNull()
  expect(document.body.textContent).toContain('Lista na fila da impressora')
  expect(document.body.textContent).not.toContain('Confirmar impressão')
})

it('recovers the identical request after a lost response and remount with a different selection', async () => {
  mocks.print.mockRejectedValueOnce(new Error('connection lost'))
  await mount(); await check(); button('Confirmar impressão').click(); await flush()
  const first = mocks.print.mock.calls[0][0]
  expect(sessionStorage.getItem(key)).not.toBeNull()
  unmount(); await mount([ids.b])
  expect(mocks.preview).toHaveBeenCalledOnce()
  expect(document.body.textContent).toContain('2 produtos selecionados')
  expect(document.body.textContent).toContain('Camiseta branca S')
  button('Recuperar confirmação').click(); await flush()
  expect(mocks.print).toHaveBeenLastCalledWith(first)
  expect(mocks.print).toHaveBeenCalledTimes(2)
  expect(sessionStorage.getItem(key)).toBeNull()
})

it('downloads the signed PDF without printing or opening a window, and delays URL cleanup', async () => {
  vi.useFakeTimers(); await mount(); button('Baixar PDF').click(); await flush()
  expect(mocks.pdf).toHaveBeenCalledWith({ snapshot: preview().snapshot, signature: preview().signature })
  expect(clickDownload).toHaveBeenCalledWith({ href: 'blob:test', download: 'conferencia.pdf' })
  expect(mocks.print).not.toHaveBeenCalled()
  expect(URL.revokeObjectURL).not.toHaveBeenCalled()
  unmount(); await vi.advanceTimersByTimeAsync(60_000)
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test')
})

it('keeps PDF available without an A4 printer and renders JSON blob errors', async () => {
  const data = preview(); data.devices = []; data.suggested_device_id = null; mocks.preview.mockResolvedValue(data)
  await mount()
  expect(document.body.textContent).toContain('Nenhuma impressora A4 ativa')
  expect(button('Confirmar impressão').disabled).toBe(true)
  // jsdom Blob lacks text(), unlike browser Blob.
  const body = new Blob(); Object.defineProperty(body, 'text', { value: async () => JSON.stringify({ detail: 'A lista expirou. Atualize a lista.' }) })
  mocks.pdf.mockRejectedValue({ response: { data: body } })
  button('Baixar PDF').click(); await flush()
  expect(document.body.textContent).toContain('A lista expirou. Atualize a lista.')
})

it('never sends a job if persisting the request fails', async () => {
  await mount(); await check()
  vi.spyOn(sessionStorage, 'setItem').mockImplementation(() => { throw new Error('quota') })
  button('Confirmar impressão').click(); await flush()
  expect(mocks.print).not.toHaveBeenCalled()
  expect(document.body.textContent).toContain('Não foi possível guardar a solicitação')
  expect(button('Baixar PDF').disabled).toBe(false)
})

it('blocks corrupt recovery until the user explicitly checks the queue, never silently replacing it', async () => {
  sessionStorage.setItem(key, '{broken'); await mount()
  expect(mocks.preview).not.toHaveBeenCalled(); expect(mocks.print).not.toHaveBeenCalled()
  expect(button('Já conferi a fila · limpar recuperação').disabled).toBe(true)
  await check(); button('Já conferi a fila · limpar recuperação').click(); await flush()
  expect(mocks.preview).toHaveBeenCalledOnce(); expect(sessionStorage.getItem(key)).toBeNull()
})

it('limits visible rows while keeping all 5000 products in the signed PDF request', async () => {
  const data = preview()
  data.snapshot.items = Array.from({ length: 5000 }, (_, i) => ({ ...data.snapshot.items[0], id: `20000000-0000-4000-8000-${String(i).padStart(12, '0')}`, name: `Camiseta ${i}` }))
  data.snapshot.totals = { items: 5000, stock_loja: 10000, stock_deposito: 35000, unknown_loja: 0, unknown_deposito: 0 }
  mocks.preview.mockResolvedValue(data); await mount(data.snapshot.items.map(row => row.id))
  expect(document.querySelectorAll('.count-table tbody tr')).toHaveLength(25)
  expect(document.body.textContent).toContain('Página 1 de 200')
  button('Próxima').click(); await flush(); expect(document.body.textContent).toContain('Camiseta 25')
  button('Baixar PDF').click(); await flush()
  expect(mocks.pdf.mock.calls[0][0].snapshot.items).toHaveLength(5000)
})

it('rejects invalid counts before loading and fails missing item previews without partial output', async () => {
  await mount([]); expect(mocks.preview).not.toHaveBeenCalled()
  expect(document.body.textContent).toContain('Selecione de 1 a 5.000')
  unmount(); mocks.preview.mockRejectedValue({ response: { status: 409, data: { detail: 'Um produto não está mais disponível.' } } })
  await mount(); expect(document.body.textContent).toContain('Um produto não está mais disponível.')
  expect(document.querySelector('.count-table')).toBeNull(); expect(mocks.print).not.toHaveBeenCalled()
})

it('discards a late response on session changes and preserves the old user recovery', async () => {
  let resolve!: (job: typeof printJob) => void
  mocks.print.mockImplementation(() => new Promise(yes => { resolve = yes }))
  await mount(); await check(); button('Confirmar impressão').click(); await flush()
  mocks.auth.user.id = 'another-user'; await flush()
  resolve(printJob); await flush()
  expect(onClose).toHaveBeenCalledOnce()
  expect(document.querySelector('.count-table')).toBeNull()
  expect(document.body.textContent).not.toContain('Lista na fila')
  expect(sessionStorage.getItem(key)).not.toBeNull()
})

it('uses stored job PDF and explains an uncertain status without claiming physical printing', async () => {
  await mount(); await check(); button('Confirmar impressão').click(); await flush()
  mocks.job.mockResolvedValue({ ...printJob, status: 'uncertain' })
  button('Atualizar estado').click(); await flush()
  expect(document.body.textContent).toContain('Confira a fila e o papel')
  button('Baixar PDF').click(); await flush()
  expect(mocks.jobPdf).toHaveBeenCalledWith('job1'); expect(mocks.pdf).not.toHaveBeenCalled()
})

it('translates the complete dialog and does not show inventory edits', async () => {
  await mount(undefined, 'es')
  expect(document.body.textContent).toContain('2 productos seleccionados')
  expect(document.body.textContent).toContain('Tienda')
  expect(button('Confirmar impresión').disabled).toBe(true)
  expect(document.querySelector('input[type=number]')).toBeNull()
})

it('validates restored ownership and snapshot coherence including negative and missing balances', () => {
  const body = pending()
  expect(restoreCountListRequest(JSON.stringify(body), ids.user)).toEqual(body)
  expect(() => restoreCountListRequest(JSON.stringify(body), 'another-user')).toThrow()
  body.snapshot.totals.stock_deposito = 0
  expect(() => restoreCountListRequest(JSON.stringify(body), ids.user)).toThrow()
})

it.each(['inventory_count_preview_expired', 'inventory_count_device_unavailable'])('allows a new preview only when the server proves no job was queued: %s', async (code) => {
  await mount(); await check()
  mocks.print.mockRejectedValueOnce({ response: { status: 409, data: { detail: { code, message: 'Atualize a lista e confira a impressora.', not_queued: true } } } })
  button('Confirmar impressão').click(); await flush()
  expect(sessionStorage.getItem(key)).toBeNull()
  expect(document.body.textContent).toContain('Atualize a lista e confira a impressora.')
  expect(document.body.textContent).not.toContain('Recuperar confirmação')
  button('Tentar novamente').click(); await flush()
  expect(mocks.preview).toHaveBeenCalledTimes(2)
  expect(button('Confirmar impressão').disabled).toBe(true)
})

it('retains recovery for conflicts without an explicit no-job guarantee', async () => {
  await mount(); await check()
  mocks.print.mockRejectedValueOnce({ response: { status: 409, data: { detail: 'A solicitação já está em processamento.' } } })
  button('Confirmar impressão').click(); await flush()
  expect(sessionStorage.getItem(key)).not.toBeNull()
  expect(button('Recuperar confirmação').disabled).toBe(false)
})

it('keeps download available when session storage cannot be read, while blocking print', async () => {
  vi.spyOn(sessionStorage, 'getItem').mockImplementation(() => { throw new Error('storage disabled') })
  await mount(); await check()
  expect(button('Confirmar impressão').disabled).toBe(true)
  expect(button('Baixar PDF').disabled).toBe(false)
  expect(document.body.textContent).toContain('Habilite o armazenamento para imprimir')
})


it('offers the count-list PDF through native options without a print or blob download', async () => {
  mocks.native = true; mocks.share.mockResolvedValueOnce('cancelled').mockResolvedValueOnce('opened')
  await mount(); button('Opções do PDF').click(); await flush()
  expect(mocks.share).toHaveBeenCalledTimes(1); expect(URL.createObjectURL).not.toHaveBeenCalled(); expect(mocks.print).not.toHaveBeenCalled()
  expect(document.body.textContent).toContain('Compartilhamento cancelado')
  const file = mocks.share.mock.calls[0]![0] as File
  expect(file.name).toBe('conferencia.pdf'); expect(file.type).toBe('application/pdf')
  button('Opções do PDF').click(); await flush()
  expect(mocks.share).toHaveBeenCalledTimes(2)
  const current = mocks.share.mock.calls[1]![1] as () => boolean
  expect(current()).toBe(true); unmount(); expect(current()).toBe(false)
})
