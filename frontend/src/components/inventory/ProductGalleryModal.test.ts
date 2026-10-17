import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, ref, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import ProductGalleryModal from './ProductGalleryModal.vue'
import type { InventoryItem } from '@/services/api'

const api = vi.hoisted(() => ({ getItemPhotos: vi.fn() }))
vi.mock('@/services/api', () => ({ inventoryAPI: api }))
vi.mock('@/services/productGallery', () => ({ galleryPreview: async (value: string) => value, MAX_PRODUCT_PHOTOS: 5 }))
vi.mock('@/services/productPhoto', () => ({ catalogForStorage: async (value: string) => value }))

let app: App | undefined, root: HTMLDivElement
const item = { id: 'local', name: 'Camiseta de teste', image_data: 'cover' } as InventoryItem
const settle = async () => { await nextTick(); await Promise.resolve(); await nextTick() }
const dialog = () => document.querySelector<HTMLElement>('[role="dialog"]')!
function mount() {
  const open = ref(false)
  app = createApp({ render: () => h('main', [
    h('button', { onClick: () => { open.value = true } }, 'Abrir foto'),
    open.value ? h(ProductGalleryModal, { item, onClose: () => { open.value = false } }) : null,
  ]) })
  app.use(createI18n({ legacy: false, locale: 'pt', messages: { pt: {} } })).mount(root)
  const opener = root.querySelector('button')!
  opener.focus(); opener.click()
  return opener
}
beforeEach(() => {
  root = document.createElement('div'); document.body.append(root)
  document.body.style.overflow = 'auto'
  api.getItemPhotos.mockResolvedValue({ additional_images: ['side'] })
  vi.spyOn(HTMLElement.prototype, 'getClientRects').mockReturnValue([{}] as unknown as DOMRectList)
})
afterEach(() => {
  app?.unmount(); app = undefined; root.remove()
  document.body.style.overflow = ''; vi.clearAllMocks(); vi.restoreAllMocks()
})

it.each(['close', 'backdrop', 'escape'])('opens outside the list and restores focus and scrolling via %s', async method => {
  const opener = mount(); await settle()
  expect(root.querySelector('[role="dialog"]')).toBeNull()
  expect(dialog().parentElement?.parentElement).toBe(document.body)
  expect(document.body.style.overflow).toBe('hidden')
  expect(document.activeElement).toBe(dialog())
  expect(dialog().querySelector('.gallery-main')?.getAttribute('src')).toBe('cover')
  dialog().querySelector<HTMLButtonElement>('[aria-label="Foto 2 do produto"]')!.click(); await settle()
  expect(dialog().querySelector('.gallery-main')?.getAttribute('src')).toBe('side')
  expect(dialog()).not.toBeNull() // Clicking the gallery itself must not dismiss it.
  if (method === 'close') dialog().querySelector<HTMLButtonElement>('[data-dialog-close]')!.click()
  else if (method === 'backdrop') dialog().parentElement!.click()
  else dialog().dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
  await settle()
  expect(dialog()).toBeNull()
  expect(document.body.style.overflow).toBe('auto')
  expect(document.activeElement).toBe(opener)
  opener.click(); await settle()
  expect(dialog()).not.toBeNull()
  app!.unmount(); app = undefined; await settle()
  expect(dialog()).toBeNull()
  expect(document.body.style.overflow).toBe('auto')
})

it('can close during loading and a late response cannot reopen or lock the list', async () => {
  let resolve!: (value: { additional_images: string[] }) => void
  api.getItemPhotos.mockReturnValue(new Promise(done => { resolve = done }))
  mount(); await settle()
  expect(dialog().textContent).toContain('Carregando fotos')
  dialog().querySelector<HTMLButtonElement>('[data-dialog-close]')!.click(); await settle()
  resolve({ additional_images: ['side'] }); await settle()
  expect(dialog()).toBeNull(); expect(document.body.style.overflow).toBe('auto')
})

it('keeps the cover and closing controls available when extra photos fail', async () => {
  api.getItemPhotos.mockRejectedValue(new Error('offline'))
  mount(); await settle()
  expect(dialog().querySelector('[role="alert"]')).not.toBeNull()
  expect(dialog().querySelector('.gallery-main')?.getAttribute('src')).toBe('cover')
  dialog().querySelector<HTMLButtonElement>('[data-dialog-close]')!.click(); await settle()
  expect(dialog()).toBeNull(); expect(document.body.style.overflow).toBe('auto')
})
