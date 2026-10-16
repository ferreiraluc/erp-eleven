import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import PDVReceiptModal from './PDVReceiptModal.vue'

const receipts = vi.hoisted(() => ({ preview: vi.fn(), pdf: vi.fn(), state: vi.fn(), print: vi.fn() }))
vi.mock('@/services/pdvReceipts', () => ({ pdvReceipts: receipts }))
const pdfBytes = new TextEncoder().encode('%PDF-1.4\nreceipt fixture\n%%EOF').buffer as ArrayBuffer
const downloadLink = () => document.querySelector<HTMLAnchorElement>('.receipt-pdf-controls a[download]')
const preview = { title: 'ELEVEN', code: 'ABCDEF1234', items: [], payments: [], footer: [] }
let app: App | undefined, root: HTMLDivElement
const settle = async () => { for (let n = 0; n < 12; n++) { await nextTick(); await Promise.resolve() } }
function button(label: string) {
  return Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === label)
}
async function mount(id = 'sale-one') {
  app = createApp(PDVReceiptModal, { sale: { id } })
  app.mount(root); await settle()
}
const originalShare = Object.getOwnPropertyDescriptor(navigator, 'share')
const originalCanShare = Object.getOwnPropertyDescriptor(navigator, 'canShare')
const share = vi.fn(), canShare = vi.fn()
beforeEach(() => {
  vi.resetAllMocks()
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:local-download-only')
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  // Reproduce a browser that advertises sharing but refuses a valid PDF.
  share.mockRejectedValue(new DOMException('Permission denied', 'NotAllowedError'))
  canShare.mockReturnValue(true)
  Object.defineProperty(navigator, 'share', { configurable: true, value: share })
  Object.defineProperty(navigator, 'canShare', { configurable: true, value: canShare })
  root = document.createElement('div'); document.body.append(root)
  receipts.preview.mockResolvedValue(preview)
  receipts.pdf.mockResolvedValue(pdfBytes)
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

describe('restored receipt file-download flow', () => {
  it.each(['new-pdv-sale', 'existing-sale'])('downloads the named PDF for %s without calling the refused share API', async id => {
    const syntheticClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const popup = vi.spyOn(window, 'open').mockImplementation(() => null)
    const print = vi.spyOn(window, 'print').mockImplementation(() => {})
    await mount(id)
    expect(receipts.pdf).toHaveBeenCalledExactlyOnceWith(id)
    const link = downloadLink()!
    expect(link.textContent).toBe('📄 Salvar PDF')
    expect(link.download).toBe('eleven-ticket-ABCDEF1234.pdf')
    expect(link.getAttribute('href')).toBe('blob:local-download-only')
    expect(link.target).toBe('')
    expect(document.body.textContent).not.toContain('blob:')
    const file = vi.mocked(URL.createObjectURL).mock.calls[0]![0] as File
    expect(file.name).toBe(link.download)
    expect(file.type).toBe('application/pdf')
    expect(new Uint8Array(await file.arrayBuffer())).toEqual(new Uint8Array(pdfBytes))

    let browserActionAllowed = false
    document.addEventListener('click', event => {
      browserActionAllowed = !event.defaultPrevented
      // jsdom cannot download. Only this test cancels the browser default.
      event.preventDefault()
    }, { once: true })
    link.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))
    await settle()
    expect(browserActionAllowed).toBe(true)
    expect(syntheticClick).not.toHaveBeenCalled()
    expect(share).not.toHaveBeenCalled(); expect(canShare).not.toHaveBeenCalled()
    expect(popup).not.toHaveBeenCalled(); expect(print).not.toHaveBeenCalled()
    expect(receipts.print).not.toHaveBeenCalled()
    expect(receipts.pdf).toHaveBeenCalledTimes(1)
    expect(document.querySelector('[role="status"]')?.textContent).toContain('Download solicitado.')
    expect(document.querySelector('[role="status"]')?.textContent).toContain('Downloads ou Arquivos')
    expect(document.querySelector('[role="alert"]')).toBeNull()
  })

  it('keeps the download available without any native sharing API', async () => {
    Object.defineProperty(navigator, 'share', { configurable: true, value: undefined })
    Object.defineProperty(navigator, 'canShare', { configurable: true, value: undefined })
    await mount()
    expect(downloadLink()?.download).toBe('eleven-ticket-ABCDEF1234.pdf')
    expect(button('Compartilhar PDF')).toBeUndefined()
    expect(document.querySelector('[role="status"]')?.textContent).not.toContain('Download solicitado.')
  })

  it('does not offer invalid data as a PDF or start a print', async () => {
    receipts.pdf.mockResolvedValue(new TextEncoder().encode('<html>Login</html>').buffer)
    await mount()
    expect(downloadLink()).toBeNull()
    expect(URL.createObjectURL).not.toHaveBeenCalled()
    expect(document.querySelector('[role="alert"]')?.textContent).toContain('não é um PDF completo')
    expect(button('Preparar PDF')?.disabled).toBe(false)
    expect(share).not.toHaveBeenCalled(); expect(receipts.print).not.toHaveBeenCalled()
  })

  it('recovers preparation errors without starting a download until the next explicit tap', async () => {
    const download = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    receipts.pdf.mockRejectedValueOnce(new Error('offline'))
    await mount()
    expect(downloadLink()).toBeNull()
    expect(document.querySelector('.receipt-pdf-controls [role="alert"]')).not.toBeNull()
    button('Preparar PDF')!.click(); await settle()
    expect(receipts.pdf).toHaveBeenCalledTimes(2)
    expect(downloadLink()?.download).toBe('eleven-ticket-ABCDEF1234.pdf')
    expect(document.querySelector('.receipt-pdf-controls [role="alert"]')).toBeNull()
    expect(download).not.toHaveBeenCalled(); expect(share).not.toHaveBeenCalled()
  })

  it('ignores a PDF that arrives after the receipt closes', async () => {
    let resolvePDF!: (pdf: ArrayBuffer) => void
    receipts.pdf.mockImplementationOnce(() => new Promise<ArrayBuffer>(resolve => { resolvePDF = resolve }))
    await mount()
    expect(button('Preparando PDF…')?.disabled).toBe(true)
    app!.unmount(); app = undefined
    resolvePDF(pdfBytes); await settle()
    expect(URL.createObjectURL).not.toHaveBeenCalled()
    expect(document.querySelector('.receipt-overlay')).toBeNull()
  })

  it('keeps a started download readable briefly after closing, then releases its URL', async () => {
    vi.useFakeTimers()
    await mount()
    app!.unmount(); app = undefined
    expect(URL.revokeObjectURL).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(10000)
    expect(URL.revokeObjectURL).toHaveBeenCalledExactlyOnceWith('blob:local-download-only')
  })
})
