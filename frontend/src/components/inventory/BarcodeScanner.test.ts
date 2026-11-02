import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import BarcodeScanner from './BarcodeScanner.vue'
import { chooseDropdown } from '@/test/dropdown'

const camera = vi.hoisted(() => ({ start: vi.fn(), stop: vi.fn(), capabilities: vi.fn(), settings: vi.fn(), apply: vi.fn(), enumerate: vi.fn() }))
vi.mock('html5-qrcode', () => ({ Html5Qrcode: class {
  start = camera.start
  stop = camera.stop
  getRunningTrackCapabilities = camera.capabilities
  getRunningTrackSettings = camera.settings
  applyVideoConstraints = camera.apply
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
beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear()
  camera.start.mockResolvedValue(undefined); camera.stop.mockResolvedValue(undefined)
  camera.capabilities.mockReturnValue({}); camera.settings.mockReturnValue({ deviceId: 'back' })
  camera.apply.mockResolvedValue(undefined); camera.enumerate.mockResolvedValue([])
  vi.stubGlobal('navigator', { mediaDevices: { enumerateDevices: camera.enumerate }, vibrate: vi.fn() })
})
afterEach(() => { app?.unmount(); app = null; root?.remove(); vi.unstubAllGlobals(); localStorage.clear() })

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

it('retries an unsupported resolution once without advanced constraints, retaining all barcode formats', async () => {
  camera.start.mockRejectedValueOnce(new DOMException('Resolution unsupported', 'OverconstrainedError'))
  await mount()
  expect(camera.start).toHaveBeenCalledTimes(2)
  expect(camera.start.mock.calls[0][1].videoConstraints).toMatchObject({ width: { ideal: 1280 }, height: { ideal: 720 } })
  expect(camera.start.mock.calls[1][0]).toEqual({ facingMode: 'environment' })
  expect(camera.start.mock.calls[1][1]).not.toHaveProperty('videoConstraints')
  expect(camera.start.mock.calls[1][1]).not.toHaveProperty('formatsToSupport')
  camera.start.mock.calls[1][2]('7891234567895')
  expect(detected).toHaveBeenCalledWith('7891234567895')
})

it.each(['NotAllowedError', 'PermissionDeniedError'])('never repeats a denied camera request (%s), and preserves manual entry', async name => {
  camera.start.mockRejectedValue(new DOMException('Permission denied', name))
  await mount()
  expect(camera.start).toHaveBeenCalledTimes(1)
  expect(root.querySelector('.camera-error')).not.toBeNull()
  const input = root.querySelector<HTMLInputElement>('.manual-input')!
  input.value = '  INV-MANUAL  '; input.dispatchEvent(new Event('input')); await flush()
  root.querySelector<HTMLButtonElement>('.manual-btn')!.click()
  expect(detected).toHaveBeenCalledWith('INV-MANUAL')
})

it('keeps scanning if optional continuous autofocus is refused', async () => {
  camera.capabilities.mockReturnValue({ focusMode: ['continuous'] })
  camera.apply.mockRejectedValue(new DOMException('Unsupported focus', 'OverconstrainedError'))
  await mount()
  expect(camera.apply).toHaveBeenCalledWith({ advanced: [{ focusMode: 'continuous' }] })
  expect(root.querySelector('.camera-error')).toBeNull()
  camera.start.mock.calls[0][2]('INV-FOCUS')
  expect(detected).toHaveBeenCalledWith('INV-FOCUS')
})

it('does not invent autofocus support, and keeps decoding when camera controls are unavailable', async () => {
  camera.capabilities.mockImplementation(() => { throw new Error('Older Safari') })
  await mount()
  expect(camera.apply).not.toHaveBeenCalled()
  expect(root.querySelector('.camera-error')).toBeNull()
  camera.start.mock.calls[0][2]('INV-LEGACY')
  expect(detected).toHaveBeenCalledWith('INV-LEGACY')
})

const devices = [
  { kind: 'videoinput', deviceId: 'back', label: 'Back Camera' },
  { kind: 'videoinput', deviceId: 'front', label: 'Front Camera' },
]

it('honors the saved camera, stops it when switching, and rejects frames from the old camera', async () => {
  localStorage.setItem('eleven:scanner:camera', 'front')
  camera.enumerate.mockResolvedValue(devices)
  camera.settings.mockReturnValueOnce({ deviceId: 'front' }).mockReturnValue({ deviceId: 'back' })
  await mount()
  expect(camera.start).toHaveBeenCalledTimes(1)
  expect(camera.start.mock.calls[0][0]).toBe('front')
  const oldFrame = camera.start.mock.calls[0][2]
  await chooseDropdown(root.querySelector('.erp-dropdown'), 'back'); await flush()
  expect(camera.start).toHaveBeenCalledTimes(2)
  expect(camera.start.mock.calls[1][0]).toBe('back')
  expect(camera.stop).toHaveBeenCalledTimes(1)
  expect(localStorage.getItem('eleven:scanner:camera')).toBe('back')
  oldFrame('INV-STALE')
  expect(detected).not.toHaveBeenCalled()
  camera.start.mock.calls[1][2]('INV-CURRENT')
  expect(detected).toHaveBeenCalledWith('INV-CURRENT')
})

it('does not replace a manual lens choice when the first permission-time enumeration completes late', async () => {
  let enumerated!: (devices: unknown[]) => void
  camera.enumerate.mockResolvedValueOnce(devices).mockReturnValueOnce(new Promise(resolve => { enumerated = resolve }))
  camera.settings.mockReturnValueOnce({ deviceId: 'back' }).mockReturnValue({ deviceId: 'front' })
  await mount()
  await chooseDropdown(root.querySelector('.erp-dropdown'), 'front'); await flush()
  enumerated(devices); await flush()
  expect(camera.start).toHaveBeenCalledTimes(2)
  expect(camera.start.mock.calls[1][0]).toBe('front')
})

it('does not apply a late torch control response to a newly selected camera', async () => {
  let applied!: () => void
  camera.enumerate.mockResolvedValue(devices)
  camera.settings.mockReturnValueOnce({ deviceId: 'back' }).mockReturnValue({ deviceId: 'front' })
  camera.capabilities.mockReturnValue({ torch: true })
  camera.apply.mockReturnValueOnce(new Promise<void>(resolve => { applied = resolve }))
  await mount()
  root.querySelector<HTMLButtonElement>('.camera-controls button[aria-pressed]')!.click()
  await chooseDropdown(root.querySelector('.erp-dropdown'), 'front'); await flush()
  applied(); await flush()
  expect(root.querySelector('.camera-controls button[aria-pressed]')?.getAttribute('aria-pressed')).toBe('false')
})
