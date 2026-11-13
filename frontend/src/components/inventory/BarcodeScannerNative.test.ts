import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import BarcodeScanner from './BarcodeScanner.vue'
import { NativeScannerError } from '@/services/nativeScanner'

const native = vi.hoisted(() => ({ scan: vi.fn(), web: vi.fn(), enumerate: vi.fn() }))
vi.mock('@/services/nativeScanner', async importOriginal => ({
  ...await importOriginal<typeof import('@/services/nativeScanner')>(), usesNativeScanner: () => true, scanNativeCode: native.scan,
}))
vi.mock('html5-qrcode', () => ({ Html5Qrcode: native.web }))
vi.mock('@/components/inventory/i18n', () => ({ useInventoryI18n: () => ({ tr: (s: string) => s }) }))
vi.mock('@/directives/erpDialog', () => ({ vErpDialog: {} }))
let app: App | undefined, root: HTMLDivElement
const detected = vi.fn()
async function settle() { for (let i = 0; i < 12; i++) { await Promise.resolve(); await nextTick() } }
async function mount() {
  root = document.createElement('div'); document.body.append(root)
  app = createApp(BarcodeScanner, { onBarcodeDetected: detected }); app.mount(root); await settle()
}
beforeEach(() => {
  vi.resetAllMocks(); native.scan.mockResolvedValue(null)
  vi.stubGlobal('navigator', { mediaDevices: { enumerateDevices: native.enumerate } })
})
afterEach(() => { app?.unmount(); app = undefined; root?.remove(); vi.unstubAllGlobals() })

it('uses native scanning only and emits a detected code once', async () => {
  native.scan.mockResolvedValue('INV-NATIVE')
  await mount()
  expect(detected).toHaveBeenCalledExactlyOnceWith('INV-NATIVE')
  expect(native.web).not.toHaveBeenCalled(); expect(native.enumerate).not.toHaveBeenCalled()
  expect(root.querySelector('#qr-reader')).toBeNull()
  root.querySelector<HTMLButtonElement>('.native-scanner-controls button')!.click(); await settle()
  expect(native.scan).toHaveBeenCalledTimes(1)
})

it('keeps manual entry and an explicit retry after cancellation', async () => {
  await mount()
  expect(root.textContent).toContain('Leitura cancelada')
  expect(root.querySelector('[role=alert]')).toBeNull()
  expect(detected).not.toHaveBeenCalled()
  native.scan.mockResolvedValueOnce('INV-RETRY')
  root.querySelector<HTMLButtonElement>('.native-scanner-controls button')!.click(); await settle()
  expect(native.scan).toHaveBeenCalledTimes(2)
  expect(detected).toHaveBeenCalledExactlyOnceWith('INV-RETRY')
})

it('does not loop denied permissions and can search manually', async () => {
  native.scan.mockRejectedValue(new NativeScannerError('denied'))
  await mount()
  expect(root.querySelector('[role=alert]')?.textContent).toContain('configurações do aparelho')
  expect(native.scan).toHaveBeenCalledTimes(1)
  const input = root.querySelector<HTMLInputElement>('.manual-input')!
  input.value = '  INV-MANUAL  '; input.dispatchEvent(new Event('input')); await settle()
  root.querySelector<HTMLButtonElement>('.manual-btn')!.click()
  expect(detected).toHaveBeenCalledExactlyOnceWith('INV-MANUAL')
})

it('ignores a native result after closing and does not reopen the web camera', async () => {
  let finish!: (code: string) => void
  native.scan.mockReturnValueOnce(new Promise<string>(resolve => { finish = resolve }))
  await mount(); app!.unmount(); app = undefined
  finish('INV-LATE'); await settle()
  expect(detected).not.toHaveBeenCalled(); expect(native.web).not.toHaveBeenCalled()
})

it('never emits a late scan after a manual code has already been accepted', async () => {
  let finish!: (code: string) => void
  native.scan.mockReturnValueOnce(new Promise<string>(resolve => { finish = resolve }))
  await mount()
  const input = root.querySelector<HTMLInputElement>('.manual-input')!
  input.value = 'INV-MANUAL'; input.dispatchEvent(new Event('input')); await settle()
  root.querySelector<HTMLButtonElement>('.manual-btn')!.click()
  finish('INV-LATE'); await settle()
  expect(detected).toHaveBeenCalledExactlyOnceWith('INV-MANUAL')
})
