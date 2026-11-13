import { Capacitor } from '@capacitor/core'
import { nativeText } from './nativeMessages'

export function usesNativeScanner(): boolean { return Capacitor.isNativePlatform() }

export class NativeScannerError extends Error {
  constructor(public readonly reason: 'denied' | 'busy' | 'failed') {
    super(reason)
    this.name = 'NativeScannerError'
  }
}

let scanning = false

/** One native camera session at a time. The caller owns dismissal/stale-result guards. */
export async function scanNativeCode(): Promise<string | null> {
  if (!usesNativeScanner()) throw new NativeScannerError('failed')
  if (scanning) throw new NativeScannerError('busy')
  scanning = true
  try {
    const { CapacitorBarcodeScanner, CapacitorBarcodeScannerTypeHint, CapacitorBarcodeScannerCameraDirection,
      CapacitorBarcodeScannerScanOrientation, CapacitorBarcodeScannerAndroidScanningLibrary } = await import('@capacitor/barcode-scanner')
    const result = await CapacitorBarcodeScanner.scanBarcode({
      hint: CapacitorBarcodeScannerTypeHint.ALL,
      cameraDirection: CapacitorBarcodeScannerCameraDirection.BACK,
      scanOrientation: CapacitorBarcodeScannerScanOrientation.ADAPTIVE,
      android: { scanningLibrary: CapacitorBarcodeScannerAndroidScanningLibrary.ZXING },
      scanInstructions: nativeText('scanInstructions'),
      cancelButtonAccessibilityLabel: nativeText('cancel'),
      torchButtonOnAccessibilityLabel: nativeText('torchOn'),
      torchButtonOffAccessibilityLabel: nativeText('torchOff'),
    })
    const code = typeof result.ScanResult === 'string' ? result.ScanResult.trim() : ''
    if (code.length > 4096) throw new NativeScannerError('failed')
    return code || null
  } catch (error) {
    if (error instanceof NativeScannerError) throw error
    const code = (error as { code?: unknown })?.code
    // Codes are defined by the official Capacitor scanner on both native targets.
    if (code === 'OS-PLUG-BARC-0006') return null
    if (code === 'OS-PLUG-BARC-0007') throw new NativeScannerError('denied')
    throw new NativeScannerError('failed')
  } finally { scanning = false }
}
