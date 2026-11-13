import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import PDVReceiptModal from './PDVReceiptModal.vue'
import { NativePdfError } from '@/services/nativeFiles'

const receipts = vi.hoisted(() => ({ preview: vi.fn(), pdf: vi.fn(), state: vi.fn(), print: vi.fn(), share: vi.fn() }))
vi.mock('@/services/pdvReceipts', () => ({ pdvReceipts: receipts }))
vi.mock('@/services/nativeFiles', async importOriginal => ({
  ...await importOriginal<typeof import('@/services/nativeFiles')>(), usesNativeFiles: () => true, shareNativePdf: receipts.share,
}))
const bytes = new TextEncoder().encode('%PDF-1.4\nfixture\n%%EOF').buffer as ArrayBuffer
let app: App | undefined, root: HTMLDivElement
const settle = async () => { for (let i = 0; i < 12; i++) { await nextTick(); await Promise.resolve() } }
function button(label: string) { return Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === label) }
async function mount() { app = createApp(PDVReceiptModal, { sale: { id: 'qa-sale' } }); app.mount(root); await settle() }
beforeEach(() => {
  vi.resetAllMocks()
  root = document.createElement('div'); document.body.append(root)
  receipts.preview.mockResolvedValue({ title: 'ELEVEN', code: 'QA123', items: [], payments: [], footer: [] })
  receipts.pdf.mockResolvedValue(bytes); receipts.state.mockResolvedValue({ printer: null, job: null })
  receipts.share.mockResolvedValue('opened')
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:should-not-be-used')
  vi.spyOn(window, 'print').mockImplementation(() => {})
})
afterEach(() => { app?.unmount(); app = undefined; root.remove() })

it('shares the prepared PDF only after a tap, without blob downloads or browser printing', async () => {
  await mount()
  expect(receipts.share).not.toHaveBeenCalled(); expect(URL.createObjectURL).not.toHaveBeenCalled()
  expect(document.querySelector('a[download]')).toBeNull(); expect(button('🖨 Neste aparelho')).toBeUndefined()
  button('Opções do PDF')!.click(); await settle()
  expect(receipts.share).toHaveBeenCalledTimes(1)
  const file = receipts.share.mock.calls[0]![0] as File
  expect(file.name).toBe('eleven-ticket-QA123.pdf'); expect(file.type).toBe('application/pdf')
  expect(new Uint8Array(await file.arrayBuffer())).toEqual(new Uint8Array(bytes))
  expect(window.print).not.toHaveBeenCalled(); expect(receipts.print).not.toHaveBeenCalled()
  expect(document.querySelector('.receipt-pdf-controls [role=status]')?.textContent).toContain('Arquivo encaminhado')
})

it('keeps cancellation recoverable and does not offer multiple sheets on repeated taps', async () => {
  let finish!: (result: string) => void
  receipts.share.mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  await mount(); button('Opções do PDF')!.click(); await settle()
  expect(button('Preparando arquivo…')?.disabled).toBe(true)
  button('Preparando arquivo…')!.click(); await settle()
  expect(receipts.share).toHaveBeenCalledTimes(1)
  finish('cancelled'); await settle()
  expect(document.querySelector('.receipt-pdf-controls [role=alert]')).toBeNull()
  expect(document.body.textContent).toContain('Compartilhamento cancelado')
  button('Opções do PDF')!.click(); await settle()
  expect(receipts.share).toHaveBeenCalledTimes(2); expect(receipts.pdf).toHaveBeenCalledTimes(1)
})

it('shows a native failure and allows retry without repeating sale/print operations', async () => {
  receipts.share.mockRejectedValueOnce(new NativePdfError('failed'))
  await mount(); button('Opções do PDF')!.click(); await settle()
  expect(document.querySelector('.receipt-pdf-controls [role=alert]')?.textContent).toContain('Tente novamente')
  button('Opções do PDF')!.click(); await settle()
  expect(document.querySelector('.receipt-pdf-controls [role=alert]')).toBeNull()
  expect(receipts.print).not.toHaveBeenCalled(); expect(receipts.pdf).toHaveBeenCalledTimes(1)
})

it('invalidates the callback supplied to preparation once the receipt is closed', async () => {
  await mount(); button('Opções do PDF')!.click(); await settle()
  const isCurrent = receipts.share.mock.calls[0]![1] as () => boolean
  expect(isCurrent()).toBe(true)
  app!.unmount(); app = undefined
  expect(isCurrent()).toBe(false)
})
