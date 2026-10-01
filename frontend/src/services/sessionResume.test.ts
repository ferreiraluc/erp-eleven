import { describe, expect, it, vi } from 'vitest'
import { resumeVerifiedSession } from './sessionResume'
import type { useAuthStore } from '@/stores/auth'
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes }); return { promise, resolve } }
function authFixture(check: Promise<boolean>) { return { token: 'original', status: 'authenticated', isLoading: false, user: { must_change_password: false }, ensureSession: vi.fn(() => check) } as unknown as ReturnType<typeof useAuthStore> }
describe('Resume validation ownership', () => {
  it.each([true, false])('does not navigate a new account after an old validation resolves %s', async valid => {
    const check = deferred<boolean>(), auth = authFixture(check.promise), replace = vi.fn()
    const pending = resumeVerifiedSession(auth, { replace })
    auth.token = 'new-account'; auth.user!.must_change_password = true
    check.resolve(valid); await pending
    expect(replace).not.toHaveBeenCalled()
  })
  it('does not cancel a new pending login after old local expiry', async () => {
    const check = deferred<boolean>(), auth = authFixture(check.promise), replace = vi.fn()
    const pending = resumeVerifiedSession(auth, { replace })
    auth.token = null; auth.status = 'guest'; auth.isLoading = true
    check.resolve(false); await pending
    expect(replace).not.toHaveBeenCalled()
  })
  it('routes a genuine expiry to login even though validation cleared its original token', async () => {
    const check = deferred<boolean>(), auth = authFixture(check.promise), replace = vi.fn()
    const pending = resumeVerifiedSession(auth, { replace })
    auth.token = null; auth.status = 'guest'
    check.resolve(false); await pending
    expect(replace).toHaveBeenCalledWith('/login')
  })
  it('keeps normal verified forms in place and routes only a current password requirement', async () => {
    const auth = authFixture(Promise.resolve(true)), replace = vi.fn()
    await resumeVerifiedSession(auth, { replace }); expect(replace).not.toHaveBeenCalled()
    auth.user!.must_change_password = true
    await resumeVerifiedSession(auth, { replace }); expect(replace).toHaveBeenCalledWith('/conta')
  })
})
