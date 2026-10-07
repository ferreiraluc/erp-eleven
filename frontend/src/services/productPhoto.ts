import api from './api'

export interface ProductPhotoFields {
  name: string; description: string; category: string; color: string; brand: string; size: string
}
export interface ProductPhotoAnalysis extends ProductPhotoFields {
  single_product: boolean; brand_evidence: string; size_evidence: string
}
export interface ProductPhotoResult extends ProductPhotoFields { image_data: string; original_image?: string }
export const photoStatus = async () => (await api.get<{ editing_available: boolean; model: string }>('/api/product-photo/status')).data
export const analyzePhoto = async (image: string, signal: AbortSignal) =>
  (await api.post<ProductPhotoAnalysis>('/api/product-photo/analyze', { image }, { signal, timeout: 45000 })).data
export const generateCatalog = async (image: string, signal: AbortSignal) =>
  (await api.post<{ image: string; model: string; estimated_cost_usd: number | null }>(
    '/api/product-photo/catalog', { image, confirmed: true }, { signal, timeout: 145000 })).data

export function photoError(error: unknown): string {
  const value = error as { response?: { data?: { detail?: unknown } } }
  const code = value.response?.data?.detail
  return typeof code === 'string' && ['invalid_image', 'analysis_unavailable', 'invalid_analysis', 'in_progress',
    'rate_limit', 'edit_unavailable', 'edit_uncertain', 'provider_error'].includes(code) ? code : 'provider_error'
}

export function imageElement(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('invalid_image'))
    image.src = url
  })
}
function canvas(width: number, height: number) {
  const node = document.createElement('canvas')
  node.width = width; node.height = height
  const context = node.getContext('2d', { willReadFrequently: true })
  if (!context) throw new Error('cutout_failed')
  return { node, context }
}
export async function preparePhoto(file: File): Promise<string> {
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 15 * 1024 * 1024) throw new Error('invalid_image')
  const url = URL.createObjectURL(file)
  try {
    const image = await imageElement(url)
    if (Math.min(image.naturalWidth, image.naturalHeight) < 64 || image.naturalWidth * image.naturalHeight > 48_000_000) throw new Error('invalid_image')
    const ratio = Math.min(1, 1600 / Math.max(image.naturalWidth, image.naturalHeight))
    const { node, context } = canvas(Math.round(image.naturalWidth * ratio), Math.round(image.naturalHeight * ratio))
    context.fillStyle = '#fff'; context.fillRect(0, 0, node.width, node.height)
    context.drawImage(image, 0, 0, node.width, node.height)
    return node.toDataURL('image/jpeg', 0.88)
  } finally { URL.revokeObjectURL(url) }
}

export function foregroundBounds(mask: Float32Array, width: number, height: number) {
  if (mask.length !== width * height) throw new Error('cutout_failed')
  let left = width, top = height, right = -1, bottom = -1, count = 0
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const value = mask[y * width + x]
    if (!Number.isFinite(value)) throw new Error('cutout_failed')
    if (value > 0.15) { left = Math.min(left, x); top = Math.min(top, y); right = Math.max(right, x); bottom = Math.max(bottom, y); count++ }
  }
  if (count < width * height * 0.01 || count > width * height * 0.98) throw new Error('cutout_failed')
  return { left, top, width: right - left + 1, height: bottom - top + 1 }
}

export async function cutoutPhoto(source: string, signal: AbortSignal): Promise<string> {
  const image = await imageElement(source)
  if (signal.aborted) throw new DOMException('Aborted', 'AbortError')
  const small = canvas(320, 320)
  small.context.drawImage(image, 0, 0, 320, 320)
  const pixels = small.context.getImageData(0, 0, 320, 320).data
  const input = new Float32Array(3 * 320 * 320)
  let max = 1
  for (let i = 0; i < pixels.length; i += 4) max = Math.max(max, pixels[i], pixels[i + 1], pixels[i + 2])
  const mean = [0.485, 0.456, 0.406], std = [0.229, 0.224, 0.225]
  for (let i = 0; i < 320 * 320; i++) for (let c = 0; c < 3; c++) input[c * 320 * 320 + i] = (pixels[i * 4 + c] / max - mean[c]) / std[c]
  const mask = await new Promise<Float32Array>((resolve, reject) => {
    const worker = new Worker(new URL('./productPhoto.worker.ts', import.meta.url), { type: 'module' })
    const finish = (error?: Error, result?: Float32Array) => {
      clearTimeout(timer); signal.removeEventListener('abort', abort); worker.terminate()
      if (error) reject(error); else resolve(result!)
    }
    const abort = () => finish(new DOMException('Aborted', 'AbortError'))
    const timer = setTimeout(() => finish(new Error('cutout_failed')), 90000)
    signal.addEventListener('abort', abort, { once: true })
    worker.onmessage = event => event.data.error ? finish(new Error('cutout_failed')) : finish(undefined, event.data.mask)
    worker.onerror = () => finish(new Error('cutout_failed'))
    worker.postMessage({ input }, [input.buffer])
  })
  const bounds = foregroundBounds(mask, 320, 320)
  const alpha = small.context.createImageData(320, 320)
  for (let i = 0; i < mask.length; i++) {
    alpha.data[i * 4] = alpha.data[i * 4 + 1] = alpha.data[i * 4 + 2] = 255
    alpha.data[i * 4 + 3] = Math.round(Math.max(0, Math.min(1, mask[i])) * 255)
  }
  small.context.putImageData(alpha, 0, 0)
  const cutout = canvas(image.naturalWidth, image.naturalHeight)
  cutout.context.drawImage(image, 0, 0)
  cutout.context.globalCompositeOperation = 'destination-in'
  cutout.context.drawImage(small.node, 0, 0, cutout.node.width, cutout.node.height)
  const output = canvas(1200, 1200)
  output.context.fillStyle = '#fff'; output.context.fillRect(0, 0, 1200, 1200)
  const sx = bounds.left / 320 * image.naturalWidth, sy = bounds.top / 320 * image.naturalHeight
  const sw = bounds.width / 320 * image.naturalWidth, sh = bounds.height / 320 * image.naturalHeight
  const ratio = 1040 / Math.max(sw, sh)
  output.context.drawImage(cutout.node, sx, sy, sw, sh, (1200 - sw * ratio) / 2, (1200 - sh * ratio) / 2, sw * ratio, sh * ratio)
  return output.node.toDataURL('image/jpeg', 0.88)
}

/** Bound the image stored in the existing product record without re-running AI. */
export async function catalogForStorage(source: string): Promise<string> {
  const image = await imageElement(source)
  let edge = Math.min(1200, Math.max(image.naturalWidth, image.naturalHeight))
  while (edge >= 400) {
    const ratio = edge / Math.max(image.naturalWidth, image.naturalHeight)
    const { node, context } = canvas(Math.round(image.naturalWidth * ratio), Math.round(image.naturalHeight * ratio))
    context.drawImage(image, 0, 0, node.width, node.height)
    const result = node.toDataURL('image/jpeg', 0.85)
    if (result.length <= 340000) return result
    edge = Math.floor(edge * 0.8)
  }
  throw new Error('invalid_image')
}
