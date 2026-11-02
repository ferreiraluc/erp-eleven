import { describe, expect, it } from 'vitest'
import { cameraConstraintFailure, preferredScannerCamera, scannerFocusConstraints, scannerVideoConstraints } from './scannerCamera'

describe('scanner camera preferences', () => {
  const devices = [
    { deviceId: 'front', label: 'Front Camera' },
    { deviceId: 'ultra', label: 'Back Ultra Wide Camera' },
    { deviceId: 'triple', label: 'Back Triple Camera' },
    { deviceId: 'tele', label: 'Back Telephoto Camera' },
    { deviceId: 'physical', label: 'Back Camera' },
  ]
  it('prefers the physical rear lens and honors a still-available manual selection', () => {
    expect(preferredScannerCamera(devices)).toBe('physical')
    expect(preferredScannerCamera(devices, 'tele')).toBe('tele')
    expect(preferredScannerCamera(devices, 'removed')).toBe('physical')
  })
  it.each(['Câmera traseira', 'Câmara traseira', 'Cámara trasera', 'Rear Camera'])('recognizes rear camera %s without selecting a front or ultrawide camera', label => {
    expect(preferredScannerCamera([...devices.slice(0, 4), { deviceId: 'rear', label }])).toBe('rear')
  })
  it('falls back to facingMode before permission reveals labels or device IDs', () => {
    expect(preferredScannerCamera([{ deviceId: 'hidden', label: '' }])).toBe('')
    expect(preferredScannerCamera(devices.slice(0, 4))).toBe('')
    expect(scannerVideoConstraints()).toMatchObject({ facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } })
    expect(scannerVideoConstraints('physical')).toMatchObject({ deviceId: { exact: 'physical' } })
    expect(scannerVideoConstraints('physical')).not.toHaveProperty('facingMode')
  })
})

it('only requests continuous focus when the camera advertises that capability', () => {
  expect(scannerFocusConstraints({})).toBeNull()
  expect(scannerFocusConstraints({ focusMode: ['manual', 'single-shot'] })).toBeNull()
  expect(scannerFocusConstraints({ focusMode: ['continuous'] })).toEqual({ advanced: [{ focusMode: 'continuous' }] })
})

it.each(['OverconstrainedError', 'ConstraintNotSatisfiedError', 'NotFoundError', 'DevicesNotFoundError'])('allows a compatible fallback for %s', name => {
  expect(cameraConstraintFailure(new DOMException('Camera unavailable', name))).toBe(true)
  expect(cameraConstraintFailure(`${name}: camera unavailable`)).toBe(true)
})

it.each(['NotAllowedError', 'PermissionDeniedError', 'SecurityError', 'NotReadableError', 'AbortError'])('does not retry %s as a resolution problem', name => {
  expect(cameraConstraintFailure(new DOMException('Camera denied or busy', name))).toBe(false)
})
