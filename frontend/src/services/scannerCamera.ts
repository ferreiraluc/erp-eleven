/** Prefer the physical rear camera over iPhone virtual/ultrawide lenses. */
export function preferredScannerCamera(devices: Pick<MediaDeviceInfo, 'deviceId' | 'label'>[], saved = ''): string {
  if (saved && devices.some(device => device.deviceId === saved)) return saved
  const rear = devices.filter(device => /back|rear|traseir|traser|posterior/i.test(device.label) &&
    !/ultra|telephoto|teleobjet|dual|triple|front|frontal/i.test(device.label))
  return rear.find(device => /^(back|rear) camera$|^c[aâá]mera traseira$|^c[aá]mara trasera$/i.test(device.label))?.deviceId || rear[0]?.deviceId || ''
}

export function scannerVideoConstraints(deviceId = ''): MediaTrackConstraints {
  return {
    ...(deviceId ? { deviceId: { exact: deviceId } } : { facingMode: { ideal: 'environment' } }),
    width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30 },
  }
}

export type ScannerCapabilities = MediaTrackCapabilities & {
  focusMode?: string[]
  torch?: boolean
  zoom?: { min: number; max: number; step?: number }
}

export function scannerFocusConstraints(capabilities: ScannerCapabilities): MediaTrackConstraints | null {
  return capabilities.focusMode?.includes('continuous')
    ? { advanced: [{ focusMode: 'continuous' } as MediaTrackConstraintSet] } : null
}

export function cameraConstraintFailure(error: unknown): boolean {
  const text = error instanceof Error ? `${error.name} ${error.message}` : String(error)
  return /Overconstrained|ConstraintNotSatisfied|NotFoundError|DevicesNotFoundError/i.test(text)
}
