import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import BarcodeScanner from './BarcodeScanner.vue'

const camera = vi.hoisted(() => ({ start: vi.fn(), stop: vi.fn() }))
vi.mock('html5-qrcode', () => ({ Html5Qrcode: class {
  start = camera.start
  stop = camera.stop
} }))
vi.mock('@/components/inventory/i18n', () => ({ useInventoryI18n: () => ({ tr: (s: string) => s }) }))
vi.mock('@/directives/erpDialog', () => ({ vErpDialog: {} }))
let app: App | null, root: HTMLDivElement
const detected = vi.fn()
async function flush() { for (let i = 0; i < 12; i++) { await Promise.resolve(); await nextTick() } }
async function mount() {
  root = document.createElement('div'); document.body.append(root)
  app = createApp(BarcodeScanner, { onBarcodeDetected: detected }); app.mount(root)
  await vi.waitFor(() => expect(camera.start).toHaveBeenCalled())
  await flush()
}
beforeEach(() => { vi.resetAllMocks(); camera.start.mockResolvedValue(undefined); camera.stop.mockResolvedValue(undefined) })
afterEach(() => { app?.unmount(); app = null; root?.remove() })

it('accepts a QR only once when consecutive camera frames detect the same code', async () => {
  await mount()
  const success = camera.start.mock.calls[0][2]
  success('INV-A7K4P2'); success('INV-A7K4P2')
  expect(detected).toHaveBeenCalledTimes(1)
  expect(detected).toHaveBeenCalledWith('INV-A7K4P2')
  expect(camera.stop).toHaveBeenCalled()
})

it('stops a camera that finishes starting after the user closes the scanner', async () => {
  let resolve!: () => void
  camera.start.mockReturnValue(new Promise<void>(done => { resolve = done }))
  camera.stop.mockImplementationOnce(() => { throw new Error('Not started yet') })
  await mount()
  app!.unmount(); app = null
  resolve(); await flush()
  expect(camera.stop).toHaveBeenCalledTimes(2)
  expect(detected).not.toHaveBeenCalled()
})
