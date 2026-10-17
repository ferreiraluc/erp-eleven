import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, reactive, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import ProductGallery from './ProductGallery.vue'
import ItemFormModal from './ItemFormModal.vue'
const mock = vi.hoisted(() => ({ prepare: vi.fn(), photos: vi.fn(), update: vi.fn() }))
vi.mock('@/services/productGallery', () => ({ MAX_PRODUCT_PHOTOS: 5, prepareGalleryFile: mock.prepare, galleryPreview: async (v: string) => 'preview:' + v }))
vi.mock('@/services/productPhoto', () => ({ catalogForStorage: async (v: string) => v }))
vi.mock('@/services/api', () => ({ inventoryAPI: { getItemPhotos: mock.photos, updateItem: mock.update, getByBarcode: async () => [] }, ocrAPI: {} }))
let app: App, root: HTMLDivElement
const state = reactive({ cover: 'main', additional: ['side'] })
const flush = async () => { for (let i = 0; i < 5; i++) { await Promise.resolve(); await nextTick() } }
const button = (name: string) => Array.from(root.querySelectorAll('button')).find(b => b.textContent?.trim() === name)!
function mountForm() {
  app = createApp(ItemFormModal, { item: { id: 'fixture', name: 'Camiseta S', size: 'S', image_data: 'main', current_stock: 1, stock_loja: 1, stock_deposito: 0 } })
  app.use(createI18n({ legacy: false, locale: 'pt', messages: { pt: {} } })).mount(root)
}
function mountGallery() {
  app = createApp({ render: () => h(ProductGallery, { ...state, editable: true, expanded: true,
    'onUpdate:cover': (v: string) => state.cover = v, 'onUpdate:additional': (v: string[]) => state.additional = v }) })
  app.use(createI18n({ legacy: false, locale: 'pt', messages: { pt: {} } })).mount(root)
}
async function files(count: number) {
  const input = root.querySelector<HTMLInputElement>('input[multiple]')!
  Object.defineProperty(input, 'files', { configurable: true, value: Array.from({ length: count }, (_, i) => new File(['fixture'], 'photo-' + i + '.jpg', { type: 'image/jpeg' })) })
  input.dispatchEvent(new Event('change', { bubbles: true })); await flush()
}
beforeEach(() => {
  root = document.createElement('div'); document.body.append(root)
  state.cover = 'main'; state.additional = ['side']
  mock.prepare.mockImplementation(async (f: File) => f.name)
  mock.photos.mockResolvedValue({ additional_images: ['side'] })
  mock.update.mockResolvedValue({ id: 'fixture' })
})
afterEach(() => { app?.unmount(); root.remove(); vi.clearAllMocks() })
it('adds up to five compressed photos and rejects overflow without dropping existing photos', async () => {
  mountGallery(); await files(4)
  expect(mock.prepare).not.toHaveBeenCalled(); expect(root.textContent).toContain('limite de 5')
  await files(3)
  expect(state.additional).toEqual(['side', 'photo-0.jpg', 'photo-1.jpg', 'photo-2.jpg'])
  expect(button('＋ Adicionar fotos').disabled).toBe(true)
  expect(root.querySelectorAll('.gallery-thumb img')).toHaveLength(5)
  expect(root.querySelectorAll('.gallery-main')).toHaveLength(1)
})
it('selects the cover, removes one photo and promotes the next without losing the rest', async () => {
  mountGallery(); await flush()
  root.querySelectorAll<HTMLButtonElement>('.gallery-thumb')[1].click(); await flush()
  expect(root.querySelector('.gallery-main')?.getAttribute('src')).toBe('side')
  button('Usar como principal').click(); await flush()
  expect(state.cover).toBe('side'); expect(state.additional).toEqual(['main'])
  button('Remover foto 1').click(); await flush()
  expect(state.cover).toBe('main'); expect(state.additional).toEqual([])
})
it('processes uploads sequentially and leaves the gallery unchanged if a file fails', async () => {
  let resolve!: (v: string) => void
  mock.prepare.mockImplementationOnce(() => new Promise(r => { resolve = r })).mockRejectedValueOnce(new Error('invalid'))
  mountGallery(); await files(2)
  expect(mock.prepare).toHaveBeenCalledTimes(1)
  expect(button('Remover foto 1').disabled).toBe(true)
  resolve('first'); await flush()
  expect(state.additional).toEqual(['side'])
  expect(root.textContent).toContain('Não foi possível preparar a foto')
})
it('blocks saving on a failed gallery load and preserves the photos after retry', async () => {
  mock.photos.mockRejectedValueOnce(new Error('offline'))
  mountForm(); await flush()
  expect(button('Atualizar').disabled).toBe(true)
  expect(mock.update).not.toHaveBeenCalled()
  button('Tentar novamente').click(); await flush()
  expect(button('Atualizar').disabled).toBe(false)
  button('Atualizar').click(); await flush()
  expect(mock.update).toHaveBeenCalledWith('fixture', expect.objectContaining({ image_data: 'main', additional_images: undefined }))
})
