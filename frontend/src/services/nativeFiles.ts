import { Capacitor } from '@capacitor/core'
import { storedToken, tokenIsCurrent } from './sessionStorage'
import { nativeText } from './nativeMessages'

const cacheRoot = 'eleven-shared-pdf'
const retentionMs = 24 * 60 * 60 * 1000
const maxBytes = 20 * 1024 * 1024
let sharing = false
let generation = 0
let cacheCleanup: Promise<void> = Promise.resolve()

export function usesNativeFiles(): boolean { return Capacitor.isNativePlatform() }
export class NativePdfError extends Error {
  constructor(public readonly reason: 'invalid' | 'large' | 'session' | 'busy' | 'failed') {
    super(reason)
    this.name = 'NativePdfError'
  }
}

export function nativePdfErrorText(error: unknown): string {
  return nativeText(error instanceof NativePdfError && error.reason === 'session' ? 'pdfSession'
    : error instanceof NativePdfError && error.reason === 'large' ? 'pdfTooLarge'
    : error instanceof NativePdfError && error.reason === 'invalid' ? 'pdfInvalid'
    : error instanceof NativePdfError && error.reason === 'busy' ? 'pdfBusy' : 'pdfFailed')
}

function safePdfName(name: string): string {
  const stem = name.replace(/\.pdf$/i, '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9_-]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '').slice(0, 96)
  return `${stem || 'eleven-documento'}.pdf`
}

function base64(bytes: Uint8Array): string {
  const chunks: string[] = []
  for (let start = 0; start < bytes.length; start += 32768) chunks.push(String.fromCharCode(...bytes.subarray(start, start + 32768)))
  return btoa(chunks.join(''))
}

/** Private cache only; never touches files exported by the user to Files/Downloads. */
export function clearNativePdfCache(): Promise<void> {
  generation++
  if (!usesNativeFiles()) return Promise.resolve()
  cacheCleanup = cacheCleanup.then(async () => {
    try {
      const { Filesystem, Directory } = await import('@capacitor/filesystem')
      await Filesystem.rmdir({ path: cacheRoot, directory: Directory.Cache, recursive: true })
    } catch { /* Cache may already be absent or evicted by the OS. */ }
  })
  return cacheCleanup
}

/** Called by the native bootstrap; web sessions keep their existing download flow. */
export async function initializeNativeFileCleanup(): Promise<() => void> {
  if (!usesNativeFiles()) return () => {}
  await clearNativePdfCache()
  const onSessionCleared = () => { void clearNativePdfCache() }
  window.addEventListener('erp:session-cleared', onSessionCleared)
  return () => window.removeEventListener('erp:session-cleared', onSessionCleared)
}

async function pruneCache(): Promise<void> {
  try {
    const { Filesystem, Directory } = await import('@capacitor/filesystem')
    const entries = await Filesystem.readdir({ path: cacheRoot, directory: Directory.Cache })
    for (const entry of entries.files) {
      const match = /^(\d{13})-[a-f0-9-]+$/.exec(entry.name)
      if (entry.type !== 'directory' || !match || Number(match[1]) > Date.now() - retentionMs) continue
      await Filesystem.rmdir({ path: `${cacheRoot}/${entry.name}`, directory: Directory.Cache, recursive: true })
    }
  } catch { /* Cleanup cannot prevent sharing a current valid PDF. */ }
}

/** Share only the file. Never pass a blob URL, page URL, body, subject or customer text. */
export async function shareNativePdf(file: File, isCurrent: () => boolean = () => true): Promise<'opened' | 'cancelled'> {
  if (!usesNativeFiles()) throw new NativePdfError('failed')
  if (sharing) throw new NativePdfError('busy')
  const token = storedToken(), epoch = generation
  const current = () => generation === epoch && isCurrent() && token !== null && storedToken() === token && tokenIsCurrent(token)
  if (!current()) throw new NativePdfError('session')
  if (file.type !== 'application/pdf' || !file.size) throw new NativePdfError('invalid')
  if (file.size > maxBytes) throw new NativePdfError('large')
  sharing = true
  let directory = ''
  let offered = false
  try {
    const bytes = new Uint8Array(await file.arrayBuffer())
    if (String.fromCharCode(...bytes.subarray(0, 5)) !== '%PDF-' ||
      !String.fromCharCode(...bytes.subarray(Math.max(0, bytes.length - 1024))).includes('%%EOF')) throw new NativePdfError('invalid')
    const [{ Filesystem, Directory }, { Share }] = await Promise.all([import('@capacitor/filesystem'), import('@capacitor/share')])
    // A previous account's asynchronous cleanup must finish before the new
    // account creates its file; otherwise it could delete the new share URI.
    await cacheCleanup
    await pruneCache()
    if (!current()) throw new NativePdfError('session')
    directory = `${cacheRoot}/${Date.now()}-${crypto.randomUUID()}`
    const result = await Filesystem.writeFile({
      path: `${directory}/${safePdfName(file.name)}`, directory: Directory.Cache, recursive: true, data: base64(bytes),
    })
    if (!current()) throw new NativePdfError('session')
    // Keep the private copy briefly after the share sheet returns. Some recipient
    // apps read asynchronously; deleting immediately would hand them a dead URI.
    await Share.share({ files: [result.uri] })
    offered = true
    return 'opened'
  } catch (error) {
    if ((error as { message?: unknown })?.message === 'Share canceled') return 'cancelled'
    if (error instanceof NativePdfError) throw error
    throw new NativePdfError('failed')
  } finally {
    if (directory && !offered) {
      try {
        const { Filesystem, Directory } = await import('@capacitor/filesystem')
        await Filesystem.rmdir({ path: directory, directory: Directory.Cache, recursive: true })
      } catch { /* The cache is also pruned on the next share/session cleanup. */ }
    }
    sharing = false
  }
}
