import { Capacitor } from '@capacitor/core'
import { storedToken, tokenIsCurrent } from './sessionStorage'
import { nativeText } from './nativeMessages'

export type NativePhotoSource = 'camera' | 'photos'
let selecting = false
const maxBytes = 15 * 1024 * 1024

export function usesNativePhotos(): boolean { return Capacitor.isNativePlatform() }
export class NativePhotoError extends Error {
  constructor(public readonly reason: 'permission' | 'invalid' | 'limit' | 'session' | 'busy' | 'failed') {
    super(reason)
    this.name = 'NativePhotoError'
  }
}
export function nativePhotoErrorText(error: unknown): string {
  return nativeText(error instanceof NativePhotoError && error.reason === 'permission' ? 'photoDenied'
    : error instanceof NativePhotoError && error.reason === 'session' ? 'photoSession'
    : error instanceof NativePhotoError && error.reason === 'busy' ? 'photoBusy'
    : error instanceof NativePhotoError && error.reason === 'limit' ? 'photoLimit'
    : (error instanceof NativePhotoError && error.reason === 'invalid') || (error instanceof Error && error.message === 'invalid_image') ? 'photoInvalid' : 'photoFailed')
}

/** Recheck after decoding too: the native camera can remain open across logout. */
export function nativePhotoSession(isCurrent: () => boolean): () => boolean {
  const token = storedToken()
  return () => isCurrent() && token !== null && storedToken() === token && tokenIsCurrent(token)
}

async function photoFile(webPath: string | undefined, index: number, current: () => boolean): Promise<File> {
  if (!webPath) throw new NativePhotoError('invalid')
  const url = new URL(webPath), local = new URL(window.location.href)
  // Only the plugin's local file bridge is readable; never send an ERP token,
  // follow a remote URL, or accept an arbitrary page as a selected picture.
  if (url.protocol !== local.protocol || url.host !== local.host || !/^\/_capacitor_(?:file|content)_\//.test(url.pathname)) throw new NativePhotoError('invalid')
  const response = await fetch(url.href, { credentials: 'omit', redirect: 'error' })
  if (!current()) throw new NativePhotoError('session')
  if (!response.ok || Number(response.headers.get('content-length') || 0) > maxBytes) throw new NativePhotoError('invalid')
  const blob = await response.blob()
  if (!current()) throw new NativePhotoError('session')
  if (!blob.size || blob.size > maxBytes) throw new NativePhotoError('invalid')
  const bytes = new Uint8Array(await blob.slice(0, 12).arrayBuffer())
  const type = bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff ? 'image/jpeg'
    : bytes[0] === 0x89 && String.fromCharCode(...bytes.slice(1, 8)) === 'PNG\r\n\x1a\n' ? 'image/png'
    : String.fromCharCode(...bytes.slice(0, 4)) === 'RIFF' && String.fromCharCode(...bytes.slice(8, 12)) === 'WEBP' ? 'image/webp' : ''
  if (!type) throw new NativePhotoError('invalid')
  return new File([blob], `produto-${index + 1}.${type === 'image/jpeg' ? 'jpg' : type.slice(6)}`, { type })
}

/** Explicit native sources: capture inputs are only hints in Android WebViews.
 * Cancellation returns no files and never falls back to the other source. */
export async function selectNativePhotos(source: NativePhotoSource, options: { limit?: number; isCurrent?: () => boolean } = {}): Promise<File[]> {
  if (!usesNativePhotos()) throw new NativePhotoError('failed')
  if (selecting) throw new NativePhotoError('busy')
  const limit = Math.max(1, Math.min(5, Math.trunc(options.limit || 1)))
  const current = nativePhotoSession(options.isCurrent || (() => true))
  if (!current()) throw new NativePhotoError('session')
  selecting = true
  try {
    const { Camera, CameraDirection, EncodingType, MediaType, MediaTypeSelection } = await import('@capacitor/camera')
    if (!current()) throw new NativePhotoError('session')
    const sizing = { quality: 90, targetWidth: 1600, targetHeight: 1600, correctOrientation: true, includeMetadata: false, editable: 'no' as const }
    const results = source === 'camera'
      ? [await Camera.takePhoto({ ...sizing, saveToGallery: false, encodingType: EncodingType.JPEG, cameraDirection: CameraDirection.Rear })]
      // Camera 8.2.6's new iOS gallery returns original HEIC files and ignores
      // resizing. Its supported legacy picker decodes UIImage and writes JPEG;
      // keep this iOS-only until the new API also converts selected photos.
      : Capacitor.getPlatform() === 'ios'
        ? (await Camera.pickImages({ quality: 90, width: 1600, height: 1600, correctOrientation: true, limit }))
          .photos.map(photo => ({ type: MediaType.Photo, webPath: photo.webPath }))
        : (await Camera.chooseFromGallery({ ...sizing, mediaType: MediaTypeSelection.Photo, allowMultipleSelection: limit > 1, limit })).results
    if (!current()) throw new NativePhotoError('session')
    // Older Android pickers can ignore their UI limit. Reject instead of
    // silently dropping pictures or exceeding the product's five-photo limit.
    if (results.length > limit) throw new NativePhotoError('limit')
    const files: File[] = []
    for (const result of results) {
      if (result.type !== MediaType.Photo) throw new NativePhotoError('invalid')
      files.push(await photoFile(result.webPath, files.length, current))
      if (!current()) throw new NativePhotoError('session')
    }
    return files
  } catch (error) {
    if (error instanceof NativePhotoError) throw error
    const detail = error as { code?: string; message?: string }
    if (['OS-PLUG-CAMR-0006', 'OS-PLUG-CAMR-0020'].includes(detail?.code || '') || /\bcancel(?:led|ed)\b/i.test(detail?.message || '')) return []
    if (['OS-PLUG-CAMR-0003', 'OS-PLUG-CAMR-0005'].includes(detail?.code || '') || /permission|denied/i.test(detail?.message || '')) throw new NativePhotoError('permission')
    throw new NativePhotoError('failed')
  } finally { selecting = false }
}
