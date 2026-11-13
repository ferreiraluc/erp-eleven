import { beforeEach, expect, it, vi } from 'vitest'
import { NativeScannerError, scanNativeCode } from './nativeScanner'

const native = vi.hoisted(() => ({ enabled: true, scan: vi.fn() }))
vi.mock('@capacitor/core', () => ({ Capacitor: { isNativePlatform: () => native.enabled } }))
vi.mock('@capacitor/barcode-scanner', () => ({
  CapacitorBarcodeScanner: { scanBarcode: native.scan },
  CapacitorBarcodeScannerTypeHint: { ALL: 17 }, CapacitorBarcodeScannerCameraDirection: { BACK: 1 },
  CapacitorBarcodeScannerScanOrientation: { ADAPTIVE: 3 }, CapacitorBarcodeScannerAndroidScanningLibrary: { ZXING: 'zxing' },
}))
beforeEach(() => { native.enabled = true; native.scan.mockReset().mockResolvedValue({ ScanResult: 'INV-QA12' }) })

it('opens the rear scanner with all code formats and adaptive tablet orientation', async () => {
  native.scan.mockResolvedValue({ ScanResult: '  INV-QA12  ' })
  expect(await scanNativeCode()).toBe('INV-QA12')
  expect(native.scan).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ hint: 17, cameraDirection: 1, scanOrientation: 3, android: { scanningLibrary: 'zxing' } }))
})

it('treats official cancellation as a normal result and does not retry permission denial', async () => {
  native.scan.mockRejectedValueOnce({ code: 'OS-PLUG-BARC-0006' })
  expect(await scanNativeCode()).toBeNull()
  native.scan.mockRejectedValueOnce({ code: 'OS-PLUG-BARC-0007' })
  await expect(scanNativeCode()).rejects.toMatchObject({ reason: 'denied' })
  expect(native.scan).toHaveBeenCalledTimes(2)
})

it('does not launch a second native camera when another caller is scanning', async () => {
  let finish!: (value: { ScanResult: string }) => void
  native.scan.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
  const first = scanNativeCode()
  await vi.waitFor(() => expect(native.scan).toHaveBeenCalledTimes(1))
  await expect(scanNativeCode()).rejects.toMatchObject({ reason: 'busy' })
  finish({ ScanResult: 'INV-FIRST' })
  expect(await first).toBe('INV-FIRST')
  expect(await scanNativeCode()).toBe('INV-QA12')
})

it('never uses the scanner plugin on web and rejects an oversized result', async () => {
  native.enabled = false
  await expect(scanNativeCode()).rejects.toBeInstanceOf(NativeScannerError)
  expect(native.scan).not.toHaveBeenCalled()
  native.enabled = true
  native.scan.mockResolvedValueOnce({ ScanResult: 'x'.repeat(4097) })
  await expect(scanNativeCode()).rejects.toMatchObject({ reason: 'failed' })
})
