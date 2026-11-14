import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
const state = vi.hoisted(() => ({ native: false }))
vi.mock('./nativePush', () => ({ isNativePushPlatform: () => state.native }))
vi.mock('./notifications', () => ({ notificationsAPI: {} }))

beforeEach(() => { vi.resetModules(); state.native = false })
afterEach(() => { vi.unstubAllGlobals() })

describe('Notification audio owner', () => {
  it('never creates or resumes WebAudio in the native app', async () => {
    state.native = true
    const audio = vi.fn()
    vi.stubGlobal('AudioContext', audio)
    const { allowNotificationSound, playNotificationSound } = await import('./notificationPush')
    expect(allowNotificationSound()).toBe(false)
    expect(playNotificationSound()).toBe(false)
    expect(audio).not.toHaveBeenCalled()
  })

  it('continues allowing a visible web app to sound without replaying audio while hidden', async () => {
    const start = vi.fn(), resume = vi.fn().mockResolvedValue(undefined)
    const createOscillator = vi.fn(() => ({ frequency: { setValueAtTime: vi.fn() }, connect: vi.fn(), start, stop: vi.fn() }))
    vi.stubGlobal('AudioContext', class {
      state = 'running'; currentTime = 0; destination = {}; resume = resume
      createOscillator = createOscillator
      createGain = () => ({ gain: { setValueAtTime: vi.fn(), linearRampToValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn() }, connect: vi.fn() })
    })
    const { allowNotificationSound, playNotificationSound } = await import('./notificationPush')
    expect(allowNotificationSound()).toBe(true)
    expect(resume).toHaveBeenCalledOnce()
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' })
    expect(playNotificationSound()).toBe(false)
    expect(start).not.toHaveBeenCalled()
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
    expect(playNotificationSound()).toBe(true)
    expect(start).toHaveBeenCalledOnce()
  })
})
