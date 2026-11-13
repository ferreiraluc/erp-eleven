import { beforeEach, describe, expect, it, vi } from 'vitest'
const native = vi.hoisted(() => ({ enabled: false, addListener: vi.fn(), resume: vi.fn() }))
vi.mock('@capacitor/core', () => ({ Capacitor: { isNativePlatform: () => native.enabled } }))
vi.mock('@capacitor/app', () => ({ App: { addListener: native.addListener } }))
vi.mock('./sessionResume', () => ({ resumeVerifiedSession: native.resume }))
import { initializeNativeLifecycle } from './nativeRuntime'
beforeEach(() => { vi.clearAllMocks(); native.resume.mockResolvedValue(undefined); native.enabled = false })
describe('Native lifecycle', () => {
  it('leaves browser listeners unchanged', async () => {
    const cleanup = await initializeNativeLifecycle({} as any, {} as any)
    await cleanup(); expect(native.addListener).not.toHaveBeenCalled()
  })
  it('revalidates on resume only, preserving existing form/route handling and disposal', async () => {
    native.enabled = true
    const remove = vi.fn(); native.addListener.mockResolvedValue({ remove })
    const auth = {} as any, router = {} as any, cleanup = await initializeNativeLifecycle(auth, router)
    expect(native.addListener).toHaveBeenCalledWith('appStateChange', expect.any(Function))
    const callback = native.addListener.mock.calls[0]![1]
    callback({ isActive: false }); expect(native.resume).not.toHaveBeenCalled()
    callback({ isActive: true }); expect(native.resume).toHaveBeenCalledWith(auth, router)
    await cleanup(); callback({ isActive: true }); expect(native.resume).toHaveBeenCalledTimes(1); expect(remove).toHaveBeenCalledTimes(1)
  })
})
