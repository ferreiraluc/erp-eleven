import { beforeEach, expect, it, vi } from 'vitest'
import { clearNativePdfCache, initializeNativeFileCleanup, shareNativePdf } from './nativeFiles'

const native = vi.hoisted(() => ({ enabled: true, token: 'session-a' as string | null, valid: true,
  write: vi.fn(), remove: vi.fn(), read: vi.fn(), share: vi.fn() }))
vi.mock('@capacitor/core', () => ({ Capacitor: { isNativePlatform: () => native.enabled } }))
vi.mock('@capacitor/filesystem', () => ({ Directory: { Cache: 'CACHE' }, Filesystem: { writeFile: native.write, rmdir: native.remove, readdir: native.read } }))
vi.mock('@capacitor/share', () => ({ Share: { share: native.share } }))
vi.mock('./sessionStorage', () => ({ storedToken: () => native.token, tokenIsCurrent: () => native.valid }))
const pdf = (name = 'eleven-ticket-QA.pdf', body = '%PDF-1.4\nfixture\n%%EOF') => new File([body], name, { type: 'application/pdf' })
beforeEach(() => {
  vi.resetAllMocks(); native.enabled = true; native.token = 'session-a'; native.valid = true
  native.write.mockResolvedValue({ uri: 'file:///private/cache/receipt.pdf' }); native.remove.mockResolvedValue(undefined)
  native.read.mockResolvedValue({ files: [] }); native.share.mockResolvedValue({ activityType: 'test-target' })
})

it('shares only validated PDF bytes through a private cache URI with a safe filename', async () => {
  const file = pdf('../../Nome do cliente?.pdf')
  expect(await shareNativePdf(file)).toBe('opened')
  const write = native.write.mock.calls[0]![0]
  expect(write.path).toMatch(/^eleven-shared-pdf\/\d{13}-[a-f0-9-]+\/Nome-do-cliente.pdf$/)
  expect(write).toMatchObject({ directory: 'CACHE', recursive: true })
  expect(atob(write.data)).toBe(await file.text())
  expect(native.share).toHaveBeenCalledExactlyOnceWith({ files: ['file:///private/cache/receipt.pdf'] })
  expect(native.remove).not.toHaveBeenCalled()
})

it('prunes only expired directories owned by this feature', async () => {
  const old = `${Date.now() - 25 * 3600000}-aabb`, recent = `${Date.now()}-ccdd`
  native.read.mockResolvedValue({ files: [{ name: old, type: 'directory' }, { name: recent, type: 'directory' },
    { name: '../unrelated', type: 'directory' }, { name: 'other-file.pdf', type: 'file' }] })
  await shareNativePdf(pdf())
  expect(native.remove).toHaveBeenCalledExactlyOnceWith({ path: `eleven-shared-pdf/${old}`, directory: 'CACHE', recursive: true })
})

it('handles cancellation without reporting a failure and lets the user retry', async () => {
  native.share.mockRejectedValueOnce(new Error('Share canceled'))
  expect(await shareNativePdf(pdf())).toBe('cancelled')
  expect(native.remove).toHaveBeenCalledTimes(1)
  expect(await shareNativePdf(pdf())).toBe('opened')
  expect(native.share).toHaveBeenCalledTimes(2)
})

it('does not offer malformed, oversized, or expired-session files', async () => {
  await expect(shareNativePdf(pdf('bad.pdf', '<html>login</html>'))).rejects.toMatchObject({ reason: 'invalid' })
  const large = pdf(); Object.defineProperty(large, 'size', { value: 20 * 1024 * 1024 + 1 })
  await expect(shareNativePdf(large)).rejects.toMatchObject({ reason: 'large' })
  native.valid = false
  await expect(shareNativePdf(pdf())).rejects.toMatchObject({ reason: 'session' })
  expect(native.write).not.toHaveBeenCalled(); expect(native.share).not.toHaveBeenCalled()
})

it('prevents sharing when the modal closes or account changes during file preparation', async () => {
  let finish!: (value: { uri: string }) => void
  native.write.mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  const sharing = shareNativePdf(pdf())
  await vi.waitFor(() => expect(native.write).toHaveBeenCalled())
  native.token = 'session-b'; finish({ uri: 'file:///private/cache/old-account.pdf' })
  await expect(sharing).rejects.toMatchObject({ reason: 'session' })
  expect(native.share).not.toHaveBeenCalled(); expect(native.remove).toHaveBeenCalled()
  await expect(shareNativePdf(pdf(), () => false)).rejects.toMatchObject({ reason: 'session' })
})

it('blocks concurrent shares and releases the lock after a plugin failure', async () => {
  let finish!: (value: { uri: string }) => void
  native.write.mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  const first = shareNativePdf(pdf())
  await vi.waitFor(() => expect(native.write).toHaveBeenCalled())
  await expect(shareNativePdf(pdf())).rejects.toMatchObject({ reason: 'busy' })
  native.share.mockRejectedValueOnce(new Error('Native bridge failed')); finish({ uri: 'file:///private/cache/one.pdf' })
  await expect(first).rejects.toMatchObject({ reason: 'failed' })
  expect(await shareNativePdf(pdf())).toBe('opened')
})

it('invalidates pending work when clearing a session, even if the next account has the same token hint', async () => {
  let finish!: (value: { uri: string }) => void
  native.write.mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  const first = shareNativePdf(pdf())
  await vi.waitFor(() => expect(native.write).toHaveBeenCalled())
  await clearNativePdfCache(); finish({ uri: 'file:///private/cache/old.pdf' })
  await expect(first).rejects.toMatchObject({ reason: 'session' })
  expect(native.share).not.toHaveBeenCalled()
})

it('waits for old-account cleanup before writing the new account share file', async () => {
  let finish!: () => void
  native.remove.mockReturnValueOnce(new Promise<void>(resolve => { finish = resolve }))
  const cleanup = clearNativePdfCache()
  await vi.waitFor(() => expect(native.remove).toHaveBeenCalled())
  native.token = 'session-b'
  const pending = shareNativePdf(pdf())
  await new Promise(resolve => setTimeout(resolve, 0))
  expect(native.write).not.toHaveBeenCalled()
  finish(); await cleanup
  expect(await pending).toBe('opened')
  expect(native.write).toHaveBeenCalledTimes(1)
})

it('cleans native orphan files at bootstrap and session clear without touching the web', async () => {
  const cleanup = await initializeNativeFileCleanup()
  expect(native.remove).toHaveBeenCalledExactlyOnceWith({ path: 'eleven-shared-pdf', directory: 'CACHE', recursive: true })
  window.dispatchEvent(new Event('erp:session-cleared'))
  await vi.waitFor(() => expect(native.remove).toHaveBeenCalledTimes(2))
  cleanup(); window.dispatchEvent(new Event('erp:session-cleared')); await Promise.resolve()
  expect(native.remove).toHaveBeenCalledTimes(2)
  native.enabled = false
  await clearNativePdfCache()
  expect(native.remove).toHaveBeenCalledTimes(2)
})
