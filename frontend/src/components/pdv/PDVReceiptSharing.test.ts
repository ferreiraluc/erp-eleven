import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import PDVReceiptModal from './PDVReceiptModal.vue'

const receipts = vi.hoisted(() => ({ preview: vi.fn(), pdf: vi.fn(), state: vi.fn(), print: vi.fn() }))
vi.mock('@/services/pdvReceipts', () => ({ pdvReceipts: receipts }))
const preview = { title: 'ELEVEN', code: 'ABCDEF1234', items: [], payments: [], footer: [] }
let app: App | undefined, root: HTMLDivElement
const settle = async () => { for (let n = 0; n < 12; n++) { await nextTick(); await Promise.resolve() } }
function button(label: string) {
  return Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === label)
}
async function mount() {
  app = createApp(PDVReceiptModal, { sale: { id: 'sale-one' } })
  app.mount(root); await settle()
}
function enableSharing() {
  const share = vi.fn().mockResolvedValue(undefined), canShare = vi.fn().mockReturnValue(true)
  Object.defineProperty(navigator, 'share', { configurable: true, value: share })
  Object.defineProperty(navigator, 'canShare', { configurable: true, value: canShare })
  return { share, canShare }
}
const originalShare = Object.getOwnPropertyDescriptor(navigator, 'share')
const originalCanShare = Object.getOwnPropertyDescriptor(navigator, 'canShare')
beforeEach(() => {
  vi.resetAllMocks()
  Object.defineProperty(navigator, 'share', { configurable: true, value: undefined })
  Object.defineProperty(navigator, 'canShare', { configurable: true, value: undefined })
  root = document.createElement('div'); document.body.append(root)
  receipts.preview.mockResolvedValue(preview)
  receipts.pdf.mockResolvedValue(new Blob(['%PDF-1.4\nreceipt fixture'], { type: 'application/pdf' }))
  receipts.state.mockResolvedValue({ printer: null, job: null })
})
afterEach(() => {
  app?.unmount(); app = undefined; root.remove()
  vi.useRealTimers()
  if (originalShare) Object.defineProperty(navigator, 'share', originalShare)
  else Reflect.deleteProperty(navigator, 'share')
  if (originalCanShare) Object.defineProperty(navigator, 'canShare', originalCanShare)
  else Reflect.deleteProperty(navigator, 'canShare')
})

describe('sharing a ticket as a file', () => {
  it('shares only the named PDF, on the tap, without a URL, text, title, download or print', async () => {
    const { share } = enableSharing()
    const objectURL = vi.spyOn(URL, 'createObjectURL')
    await mount()
    expect(share).not.toHaveBeenCalled()
    expect(receipts.pdf).toHaveBeenCalledWith('sale-one')
    button('Compartilhar PDF')!.click()
    // No network await between the gesture and the native share API (iOS).
    expect(share).toHaveBeenCalledTimes(1)
    const payload = share.mock.calls[0]![0]
    expect(Object.keys(payload)).toEqual(['files'])
    expect(payload.files).toHaveLength(1)
    expect(payload.files[0]).toBeInstanceOf(File)
    expect(payload.files[0].name).toBe('eleven-ticket-ABCDEF1234.pdf')
    expect(payload.files[0].type).toBe('application/pdf')
    expect(payload.files[0].size).toBe(new Blob(['%PDF-1.4\nreceipt fixture']).size)
    await settle()
    expect(receipts.pdf).toHaveBeenCalledTimes(1)
    expect(objectURL).not.toHaveBeenCalled()
    expect(receipts.print).not.toHaveBeenCalled()
  })

  it('requires a fresh tap after retrying preparation, instead of sharing after a slow download', async () => {
    const { share } = enableSharing()
    receipts.pdf.mockRejectedValueOnce(new Error('offline'))
    await mount()
    expect(button('Preparar PDF')).toBeDefined()
    button('Preparar PDF')!.click(); await settle()
    expect(receipts.pdf).toHaveBeenCalledTimes(2)
    expect(share).not.toHaveBeenCalled()
    button('Compartilhar PDF')!.click(); await settle()
    expect(share).toHaveBeenCalledTimes(1)
  })

  it('keeps saving available when this browser cannot share PDF files', async () => {
    const { share, canShare } = enableSharing(); canShare.mockReturnValue(false)
    const objectURL = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:download-only')
    let download = ''
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) { download = this.download })
    await mount()
    expect(button('Compartilhar PDF')).toBeUndefined()
    button('📄 Salvar PDF')!.click(); await settle()
    expect(download).toBe('eleven-ticket-ABCDEF1234.pdf')
    expect(objectURL).toHaveBeenCalledTimes(1)
    expect(share).not.toHaveBeenCalled()
    expect(receipts.pdf).toHaveBeenCalledTimes(1)
  })

  it('does not prefetch on browsers without file sharing', async () => {
    await mount()
    expect(receipts.pdf).not.toHaveBeenCalled()
    expect(button('📄 Salvar PDF')?.disabled).toBe(false)
    expect(button('Compartilhar PDF')).toBeUndefined()
  })

  it('explains cancellation or unavailable share targets beside the buttons without downloading or printing', async () => {
    const { share } = enableSharing()
    share.mockRejectedValue(new DOMException('cancelled', 'AbortError'))
    const objectURL = vi.spyOn(URL, 'createObjectURL')
    await mount(); button('Compartilhar PDF')!.click(); await settle()
    expect(document.querySelector('.receipt-pdf-controls [role="alert"]')).toBeNull()
    expect(document.querySelector('.receipt-pdf-controls [role="status"]')?.textContent).toContain('Compartilhamento cancelado ou indisponível')
    expect(objectURL).not.toHaveBeenCalled(); expect(receipts.print).not.toHaveBeenCalled()
    expect(button('Compartilhar PDF')?.disabled).toBe(false)
  })

  it('shows a recoverable error on share failure without attaching a browser link', async () => {
    const { share } = enableSharing()
    share.mockRejectedValueOnce(new DOMException('blocked', 'NotAllowedError'))
    const objectURL = vi.spyOn(URL, 'createObjectURL')
    await mount(); button('Compartilhar PDF')!.click(); await settle()
    expect(document.querySelector('.receipt-pdf-controls [role="alert"]')?.textContent).toContain('O navegador bloqueou')
    expect(objectURL).not.toHaveBeenCalled()
    button('Compartilhar PDF')!.click(); await settle()
    expect(share).toHaveBeenCalledTimes(2)
    expect(document.querySelector('.receipt-pdf-controls [role="alert"]')).toBeNull()
  })

  it('keeps PDF download usable when the native share promise never finishes', async () => {
    const { share } = enableSharing()
    share.mockImplementation(() => new Promise(() => {}))
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:download-only')
    const download = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await mount(); button('Compartilhar PDF')!.click(); await settle()
    expect(button('Abrindo compartilhamento…')?.disabled).toBe(true)
    expect(document.querySelector('.receipt-pdf-controls [role="status"]')?.textContent).toContain('Se nenhuma janela abrir')
    expect(button('📄 Salvar PDF')?.disabled).toBe(false)
    button('📄 Salvar PDF')!.click(); await settle()
    expect(download).toHaveBeenCalledTimes(1)
    expect(receipts.pdf).toHaveBeenCalledTimes(1)
    expect(share).toHaveBeenCalledTimes(1)
    expect(receipts.print).not.toHaveBeenCalled()
  })

  it('shows PDF preparation failures next to the recovery buttons', async () => {
    enableSharing(); receipts.pdf.mockRejectedValue(new Error('offline'))
    await mount()
    expect(document.querySelector('.receipt-pdf-controls [role="alert"]')).not.toBeNull()
    expect(button('Preparar PDF')?.disabled).toBe(false)
    expect(button('📄 Salvar PDF')?.disabled).toBe(false)
  })

  it('unlocks a stalled share without retrying, downloading, or accepting stale results', async () => {
    vi.useFakeTimers()
    const { share } = enableSharing()
    let rejectFirst!: (error: Error) => void
    let finishSecond!: () => void
    share.mockImplementationOnce(() => new Promise((_, reject) => { rejectFirst = reject }))
      .mockImplementationOnce(() => new Promise<void>(resolve => { finishSecond = resolve }))
    const objectURL = vi.spyOn(URL, 'createObjectURL')
    await mount(); button('Compartilhar PDF')!.click(); await settle()
    await vi.advanceTimersByTimeAsync(12000); await settle()
    expect(button('Compartilhar PDF')?.disabled).toBe(false)
    expect(document.querySelector('.receipt-pdf-controls [role="status"]')?.textContent).toContain('O aparelho ainda não respondeu')
    expect(share).toHaveBeenCalledTimes(1)
    expect(objectURL).not.toHaveBeenCalled()
    button('Compartilhar PDF')!.click(); await settle()
    rejectFirst(new DOMException('old error', 'NotAllowedError')); await settle()
    expect(button('Abrindo compartilhamento…')?.disabled).toBe(true)
    expect(document.querySelector('.receipt-pdf-controls [role="alert"]')).toBeNull()
    finishSecond(); await settle()
    expect(button('Compartilhar PDF')?.disabled).toBe(false)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('blocks duplicate taps while sharing and ignores a PDF that arrives after closing', async () => {
    const { share } = enableSharing()
    let resolveShare!: () => void
    share.mockImplementationOnce(() => new Promise<void>(resolve => { resolveShare = resolve }))
    await mount(); button('Compartilhar PDF')!.click(); button('Compartilhar PDF')!.click()
    expect(share).toHaveBeenCalledTimes(1)
    resolveShare(); await settle(); app!.unmount(); app = undefined
    let resolvePDF!: (pdf: Blob) => void
    receipts.pdf.mockImplementationOnce(() => new Promise<Blob>(resolve => { resolvePDF = resolve }))
    await mount()
    expect(button('Preparando PDF…')?.disabled).toBe(true)
    app!.unmount(); app = undefined
    resolvePDF(new Blob(['%PDF-1.4'])); await settle()
    expect(share).toHaveBeenCalledTimes(1)
    expect(document.querySelector('.receipt-overlay')).toBeNull()
  })
})
