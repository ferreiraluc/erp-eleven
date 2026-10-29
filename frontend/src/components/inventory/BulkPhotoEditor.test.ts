import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, reactive, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import BulkPhotoEditor from './BulkPhotoEditor.vue'
import type { InventoryItem } from '@/services/api'
import type { PhotoDraft } from '@/services/inventoryBulkPhotos'
import { chooseDropdown } from '@/test/dropdown'

const api = vi.hoisted(() => ({ getItem: vi.fn(), batchEdit: vi.fn(), updateItem: vi.fn() }))
const photos = vi.hoisted(() => ({
  prepareGalleryFile: vi.fn(), galleryPreview: vi.fn(), preparePhoto: vi.fn(),
  catalogForStorage: vi.fn(), photoStatus: vi.fn(), cutoutPhoto: vi.fn(),
  analyzePhoto: vi.fn(), generateCatalog: vi.fn(), photoError: vi.fn(() => 'provider_error'),
}))
vi.mock('@/services/api', () => ({ inventoryAPI: api }))
vi.mock('@/services/productGallery', () => photos)
vi.mock('@/services/productPhoto', () => photos)

let app: App | undefined
let root: HTMLDivElement
const original = 'data:image/jpeg;base64,original'
const cutout = 'data:image/jpeg;base64,cutout'
const stored = 'data:image/jpeg;base64,stored'
const oldPhoto = { image: 'data:image/jpeg;base64,old', preview: 'thumb:old' }
const items = [
  { id: 'white-s', name: 'Camiseta branca S', color: 'Branco', size: 'S', has_image: true },
  { id: 'white-m', name: 'Camiseta branca M', color: 'White', size: 'M', has_image: true },
  { id: 'blue-s', name: 'Camiseta azul S', color: 'Azul', size: 'S', has_image: true },
].map(item => ({ ...item, updated_at: '2026-10-29T00:00:00Z' })) as InventoryItem[]

async function settle() {
  for (let i = 0; i < 6; i++) await nextTick()
  await vi.dynamicImportSettled()
  await nextTick()
}
function button(label: string) {
  const found = Array.from(document.querySelectorAll<HTMLButtonElement>('button'))
    .find(element => element.textContent?.trim() === label)
  if (!found) throw new Error(`Missing button: ${label}`)
  return found
}
async function mount(options: { scope?: string; draft?: PhotoDraft; data?: InventoryItem[] } = {}) {
  root = document.createElement('div')
  document.body.append(root)
  const state = reactive({
    draft: { ...options.draft } as PhotoDraft,
    scope: options.scope || 'all',
    items: options.data || items.map(item => ({ ...item })),
  })
  const updates = vi.fn(), busy = vi.fn()
  const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp(defineComponent({
    setup: () => () => h(BulkPhotoEditor, {
      items: state.items, modelValue: state.draft, embedded: true, selectedScope: state.scope,
      'onUpdate:modelValue': (value: PhotoDraft) => { state.draft = value; updates(value) },
      onBusy: busy,
    }),
  })).use(i18n)
  app.mount(root)
  await settle()
  return { state, updates, busy, i18n }
}
async function open() {
  button('Editar foto').click()
  await settle()
}
async function useCutout() {
  button('Remover fundo · grátis').click()
  await settle()
  button('Usar foto').click()
  await settle()
}
function closeEditor() {
  const close = document.querySelector<HTMLButtonElement>('.photo-dialog [data-dialog-close]')
  if (!close) throw new Error('Photo editor is not open')
  close.click()
}

beforeEach(() => {
  api.getItem.mockImplementation(async (id: string) => ({ ...items.find(item => item.id === id), image_data: original }))
  photos.photoStatus.mockResolvedValue({ editing_available: true, model: 'gpt-image-1-mini' })
  photos.cutoutPhoto.mockResolvedValue(cutout)
  photos.catalogForStorage.mockResolvedValue(stored)
  photos.galleryPreview.mockImplementation(async (image: string) => `thumb:${image}`)
  photos.preparePhoto.mockResolvedValue(original)
  photos.prepareGalleryFile.mockResolvedValue(original)
  photos.generateCatalog.mockResolvedValue({ image: 'data:image/jpeg;base64,hanger', estimated_cost_usd: 0.006 })
})
afterEach(() => {
  app?.unmount()
  app = undefined
  root?.remove()
  vi.resetAllMocks()
})

describe('Bulk photo editing with the shared photo assistant', () => {
  it('loads only the selected original, removes its background once and stages it for all selected items', async () => {
    const { state, updates, busy } = await mount()
    expect(api.getItem).not.toHaveBeenCalled()
    await chooseDropdown(root.querySelector('button[aria-label="Foto de referência"]'), 'white-m')
    await open()
    expect(api.getItem).toHaveBeenCalledTimes(1)
    expect(api.getItem).toHaveBeenCalledWith('white-m', expect.any(AbortSignal))
    expect(photos.preparePhoto).not.toHaveBeenCalled()
    expect(photos.analyzePhoto).not.toHaveBeenCalled()
    expect(photos.generateCatalog).not.toHaveBeenCalled()
    expect(document.querySelector('.photo-fields')).toBeNull()
    expect(busy).toHaveBeenLastCalledWith(true)
    await useCutout()
    expect(photos.cutoutPhoto).toHaveBeenCalledOnce()
    expect(photos.cutoutPhoto).toHaveBeenCalledWith(original, expect.any(AbortSignal))
    expect(photos.catalogForStorage).toHaveBeenCalledWith(cutout)
    expect(Object.keys(state.draft)).toEqual(['white-s', 'white-m', 'blue-s'])
    expect(state.draft['white-s']).toEqual({ image: stored, preview: `thumb:${stored}`, operation: 'replace' })
    expect(state.draft['white-m']).toEqual(state.draft['white-s'])
    expect(state.draft['blue-s']).toEqual(state.draft['white-s'])
    expect(updates).toHaveBeenCalledOnce()
    expect(busy).toHaveBeenLastCalledWith(false)
    expect(api.batchEdit).not.toHaveBeenCalled()
    expect(api.updateItem).not.toHaveBeenCalled()
    expect(photos.generateCatalog).not.toHaveBeenCalled()
  })

  it('applies one edited photo to every selected size of a color while preserving other colors', async () => {
    const { state } = await mount({ scope: 'color:branco', draft: { 'blue-s': oldPhoto } })
    await open()
    await useCutout()
    expect(state.draft['white-s'].image).toBe(stored)
    expect(state.draft['white-m'].image).toBe(stored)
    expect(state.draft['blue-s']).toEqual(oldPhoto)
    expect(api.batchEdit).not.toHaveBeenCalled()
  })

  it('edits a prepared group directly without fetching saved photos or overwriting another group', async () => {
    const shared = { image: original, preview: 'thumb:original', operation: 'add' as const }
    const { state } = await mount({ draft: { 'white-s': shared, 'white-m': shared, 'blue-s': oldPhoto } })
    const edit = root.querySelector<HTMLButtonElement>('button[aria-label^="Editar foto de Branco"]')
    expect(edit).not.toBeNull()
    edit!.click()
    await settle()
    await useCutout()
    expect(api.getItem).not.toHaveBeenCalled()
    expect(state.draft['white-s']).toEqual({ image: stored, preview: `thumb:${stored}`, operation: 'add' })
    expect(state.draft['white-m']).toEqual(state.draft['white-s'])
    expect(state.draft['blue-s']).toEqual(oldPhoto)
  })

  it('keeps the opening IDs and operation if the scope changes while the original loads', async () => {
    let finish!: (item: InventoryItem) => void
    api.getItem.mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
    const { state, busy } = await mount({ scope: 'color:branco' })
    await chooseDropdown(root.querySelector('button[aria-label="Operação da foto"]'), 'add')
    await open()
    expect(busy).toHaveBeenLastCalledWith(true)
    state.scope = 'color:azul'
    await settle()
    finish({ ...items[0], image_data: original })
    await settle()
    await useCutout()
    expect(Object.keys(state.draft)).toEqual(['white-s', 'white-m'])
    expect(state.draft['white-s'].operation).toBe('add')
    expect(state.draft['white-m'].operation).toBe('add')
  })

  it('cancels after preview without applying the edited photo or losing prepared photos', async () => {
    const { state, updates, busy } = await mount({ draft: { 'blue-s': oldPhoto } })
    await open()
    button('Remover fundo · grátis').click()
    await settle()
    closeEditor()
    await settle()
    expect(state.draft).toEqual({ 'blue-s': oldPhoto })
    expect(updates).not.toHaveBeenCalled()
    expect(busy).toHaveBeenLastCalledWith(false)
    expect(photos.catalogForStorage).not.toHaveBeenCalled()
    expect(api.batchEdit).not.toHaveBeenCalled()
  })

  it('retains drafts and allows retry if the saved original cannot be loaded', async () => {
    api.getItem.mockRejectedValueOnce(new Error('offline'))
    const { state, updates, busy } = await mount({ scope: 'color:branco', draft: { 'blue-s': oldPhoto } })
    await open()
    expect(document.querySelector('.photo-dialog')).toBeNull()
    expect(root.querySelector('[role="alert"]')?.textContent).toBeTruthy()
    expect(state.draft).toEqual({ 'blue-s': oldPhoto })
    expect(updates).not.toHaveBeenCalled()
    expect(busy).toHaveBeenLastCalledWith(false)
    await open()
    expect(document.querySelector('.photo-dialog')).not.toBeNull()
    expect(api.getItem).toHaveBeenCalledTimes(2)
  })

  it('preserves the original and existing drafts when background removal fails', async () => {
    photos.cutoutPhoto.mockRejectedValueOnce(new Error('worker unavailable'))
    const { state, updates } = await mount({ draft: { 'blue-s': oldPhoto } })
    await open()
    button('Remover fundo · grátis').click()
    await settle()
    expect(document.querySelector('.photo-dialog [role="alert"]')?.textContent).toContain('recorte')
    expect((document.querySelector('.photo-comparison img') as HTMLImageElement).src).toBe(original)
    expect(state.draft).toEqual({ 'blue-s': oldPhoto })
    expect(updates).not.toHaveBeenCalled()
    expect(photos.generateCatalog).not.toHaveBeenCalled()
  })

  it('discards a cutout that finishes after the editor is cancelled', async () => {
    let finish!: (image: string) => void
    photos.cutoutPhoto.mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
    const { state, updates } = await mount({ draft: { 'blue-s': oldPhoto } })
    await open()
    button('Remover fundo · grátis').click()
    await settle()
    const signal = photos.cutoutPhoto.mock.calls[0][1] as AbortSignal
    closeEditor()
    await settle()
    expect(signal.aborted).toBe(true)
    finish(cutout)
    await settle()
    expect(state.draft).toEqual({ 'blue-s': oldPhoto })
    expect(updates).not.toHaveBeenCalled()
    expect(document.querySelector('.photo-dialog')).toBeNull()
  })

  it('can upload inside the editor when none of the selected products has a photo', async () => {
    const { state } = await mount({ data: items.map(item => ({ ...item, has_image: false, image_data: null })) })
    await open()
    expect(api.getItem).not.toHaveBeenCalled()
    expect(button('Remover fundo · grátis').disabled).toBe(true)
    const input = document.querySelector<HTMLInputElement>('.photo-dialog input[type="file"]')!
    Object.defineProperty(input, 'files', { value: [new File(['fixture'], 'new.jpg', { type: 'image/jpeg' })] })
    input.dispatchEvent(new Event('change', { bubbles: true }))
    await settle()
    await useCutout()
    expect(Object.keys(state.draft)).toHaveLength(3)
    expect(photos.preparePhoto).toHaveBeenCalledOnce()
    expect(photos.analyzePhoto).not.toHaveBeenCalled()
    expect(photos.generateCatalog).not.toHaveBeenCalled()
  })
})
