import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { nativePhotoSession, selectNativePhotos } from './nativePhotos'

const native = vi.hoisted(() => ({ enabled: true, token: 'session-a' as string | null, valid: true,
  camera: vi.fn(), gallery: vi.fn(), fetch: vi.fn() }))
vi.mock('@capacitor/core', () => ({ Capacitor: { isNativePlatform: () => native.enabled } }))
vi.mock('@capacitor/camera', () => ({ Camera: { takePhoto: native.camera, chooseFromGallery: native.gallery },
  CameraDirection: { Rear: 'REAR' }, EncodingType: { JPEG: 0 }, MediaType: { Photo: 0 }, MediaTypeSelection: { Photo: 0 } }))
vi.mock('./sessionStorage', () => ({ storedToken: () => native.token, tokenIsCurrent: () => native.valid }))
const path = () => `${window.location.origin}/_capacitor_file_/cache/product.jpg`
const photo = () => ({ type: 0, webPath: path(), saved: false })
const jpeg = () => new Blob([new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 0, 1, 2, 3])], { type: 'image/jpeg' })

beforeEach(() => {
  vi.resetAllMocks(); native.enabled = true; native.token = 'session-a'; native.valid = true
  native.camera.mockResolvedValue(photo()); native.gallery.mockResolvedValue({ results: [photo()] })
  native.fetch.mockImplementation(async () => ({ ok: true, headers: new Headers(), blob: async () => jpeg() }))
  vi.stubGlobal('fetch', native.fetch)
})
afterEach(() => vi.unstubAllGlobals())

it('opens the rear camera explicitly, without a gallery prompt, automatic upload or saving to the gallery', async () => {
  const files = await selectNativePhotos('camera')
  expect(native.camera).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ cameraDirection: 'REAR', saveToGallery: false,
    encodingType: 0, targetWidth: 1600, targetHeight: 1600, includeMetadata: false, editable: 'no' }))
  expect(native.gallery).not.toHaveBeenCalled()
  expect(native.fetch).toHaveBeenCalledExactlyOnceWith(path(), { credentials: 'omit', redirect: 'error' })
  expect(files).toHaveLength(1); expect(files[0].type).toBe('image/jpeg')
})

it('uses the photo-only picker with the remaining gallery capacity, and rejects old pickers that ignore it', async () => {
  native.gallery.mockResolvedValueOnce({ results: [photo(), photo()] })
  expect(await selectNativePhotos('photos', { limit: 2 })).toHaveLength(2)
  expect(native.gallery).toHaveBeenCalledWith(expect.objectContaining({ mediaType: 0, allowMultipleSelection: true, limit: 2 }))
  expect(native.camera).not.toHaveBeenCalled()
  native.gallery.mockResolvedValueOnce({ results: [photo(), photo(), photo()] })
  await expect(selectNativePhotos('photos', { limit: 2 })).rejects.toMatchObject({ reason: 'limit' })
})

it.each(['OS-PLUG-CAMR-0006', 'OS-PLUG-CAMR-0020'])('preserves cancellation (%s) without falling back to gallery and can retry', async code => {
  native.camera.mockRejectedValueOnce({ code })
  expect(await selectNativePhotos('camera')).toEqual([])
  expect(native.gallery).not.toHaveBeenCalled(); expect(native.fetch).not.toHaveBeenCalled()
  expect(await selectNativePhotos('camera')).toHaveLength(1)
})

it.each(['OS-PLUG-CAMR-0003', 'OS-PLUG-CAMR-0005'])('reports permission denied (%s) without secretly opening the other source', async code => {
  native.camera.mockRejectedValueOnce({ code })
  await expect(selectNativePhotos('camera')).rejects.toMatchObject({ reason: 'permission' })
  expect(native.gallery).not.toHaveBeenCalled(); expect(native.fetch).not.toHaveBeenCalled()
})

it('rejects remote file paths, videos, oversized and malformed results before image processing', async () => {
  native.camera.mockResolvedValueOnce({ ...photo(), webPath: 'https://example.org/private.jpg' })
  await expect(selectNativePhotos('camera')).rejects.toMatchObject({ reason: 'invalid' })
  expect(native.fetch).not.toHaveBeenCalled()
  native.camera.mockResolvedValueOnce({ ...photo(), type: 1 })
  await expect(selectNativePhotos('camera')).rejects.toMatchObject({ reason: 'invalid' })
  native.fetch.mockResolvedValueOnce({ ok: true, headers: new Headers({ 'content-length': String(16 * 1024 * 1024) }) })
  await expect(selectNativePhotos('camera')).rejects.toMatchObject({ reason: 'invalid' })
  native.fetch.mockResolvedValueOnce({ ok: true, headers: new Headers(), blob: async () => new Blob(['<html>login</html>']) })
  await expect(selectNativePhotos('camera')).rejects.toMatchObject({ reason: 'invalid' })
})

it('does not apply a late photo after the form closes or a different/expired session is active', async () => {
  let finish!: (value: ReturnType<typeof photo>) => void
  native.camera.mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  const pending = selectNativePhotos('camera')
  await vi.waitFor(() => expect(native.camera).toHaveBeenCalled())
  native.token = 'session-b'; finish(photo())
  await expect(pending).rejects.toMatchObject({ reason: 'session' })
  expect(native.fetch).not.toHaveBeenCalled()
  await expect(selectNativePhotos('camera', { isCurrent: () => false })).rejects.toMatchObject({ reason: 'session' })
  const guard = nativePhotoSession(() => true)
  native.valid = false
  expect(guard()).toBe(false)
  await expect(selectNativePhotos('camera')).rejects.toMatchObject({ reason: 'session' })
})

it('blocks double-taps and releases the lock after a native error', async () => {
  let fail!: (error: Error) => void
  native.camera.mockReturnValueOnce(new Promise((_, reject) => { fail = reject }))
  const pending = selectNativePhotos('camera')
  await vi.waitFor(() => expect(native.camera).toHaveBeenCalled())
  await expect(selectNativePhotos('photos')).rejects.toMatchObject({ reason: 'busy' })
  fail(new Error('Unavailable'))
  await expect(pending).rejects.toMatchObject({ reason: 'failed' })
  expect(await selectNativePhotos('camera')).toHaveLength(1)
})
