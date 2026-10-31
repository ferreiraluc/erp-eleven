import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import InventoryReplenishmentView from './InventoryReplenishmentView.vue'
import type { InventoryItem } from '@/services/api'
import { replenishmentRequest, type ReplenishmentProduct } from '@/services/inventoryReplenishment'
import { standardLabelLayout } from '@/test/productLabelDesign'

const mocks = vi.hoisted(() => ({
  list: vi.fn(), confirm: vi.fn(), device: vi.fn(), layouts: vi.fn(), preview: vi.fn(),
  getItem: vi.fn(), getItemPhotos: vi.fn(),
  auth: { user: { id: 'owner' }, userRole: 'ADMIN', isOwner: true },
}))
vi.mock('@/services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/api')>()),
  inventoryAPI: { getItem: mocks.getItem, getItemPhotos: mocks.getItemPhotos },
}))
vi.mock('@/services/inventoryReplenishment', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/inventoryReplenishment')>()),
  inventoryReplenishment: { list: mocks.list, confirm: mocks.confirm },
}))
vi.mock('@/services/productLabels', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/productLabels')>()),
  productLabels: { device: mocks.device, layouts: mocks.layouts, preview: mocks.preview },
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))
vi.mock('@/components/inventory/ProductThumbnail.vue', () => ({
  default: { props: ['item', 'alt'], template: '<img :alt="alt" src="thumbnail-only" />' },
}))
vi.mock('@/services/productGallery', () => ({ galleryPreview: async (value: string) => value, MAX_PRODUCT_PHOTOS: 5 }))
vi.mock('@/services/productPhoto', () => ({ catalogForStorage: async (value: string) => value }))

const product: ReplenishmentProduct = {
  id: 'photo-qa', name: 'Produto sintético com foto', inventory_code: 'INV-A7K4P2',
  size: 'M', color: 'Azul', group_key: null, stock_loja: 0, stock_deposito: 4,
  current_stock: 4, sale_price: '100.00', sale_currency: 'USD', brand: null, location: null,
  has_image: true, updated_at: '2026-10-30T10:00:00Z', blocked_reason: null,
  last_store_exit_at: null, has_store_history: false,
}
const fullProduct = { ...product, image_data: 'original-cover' } as unknown as InventoryItem
let app: App | undefined, root: HTMLDivElement
const photo = () => root.querySelector<HTMLButtonElement>('.product-photo')!
const dialog = () => document.querySelector<HTMLElement>('.gallery-dialog')
async function settle() {
  for (let index = 0; index < 10; index++) { await Promise.resolve(); await nextTick() }
}
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(done => { resolve = done })
  return { promise, resolve }
}
async function mount(locale = 'pt') {
  root = document.createElement('div'); document.body.append(root)
  app = createApp(InventoryReplenishmentView)
  app.use(createI18n({ legacy: false, locale, messages: {} }))
  app.config.globalProperties.$router = createRouter({ history: createMemoryHistory(), routes: [] })
  app.mount(root); await settle()
}
async function openPhoto() {
  photo().focus(); photo().click(); await settle()
}
beforeEach(() => {
  vi.resetAllMocks()
  sessionStorage.clear(); localStorage.clear()
  mocks.auth = reactive({ user: { id: 'owner' }, userRole: 'ADMIN', isOwner: true })
  mocks.list.mockResolvedValue({ items: [product], total: 1, page: 1, page_size: 40 })
  mocks.device.mockResolvedValue({ device: { id: 'zebra', name: 'Zebra QA', last_seen_at: null } })
  mocks.layouts.mockResolvedValue([standardLabelLayout()])
  mocks.getItem.mockResolvedValue(fullProduct)
  mocks.getItemPhotos.mockResolvedValue({ additional_images: ['original-side'] })
  document.body.style.overflow = 'auto'
  vi.spyOn(HTMLElement.prototype, 'getClientRects').mockReturnValue([{}] as unknown as DOMRectList)
  vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
})
afterEach(() => {
  app?.unmount(); app = undefined; root?.remove()
  document.body.style.overflow = ''; vi.restoreAllMocks()
})

it.each(['close', 'backdrop', 'escape'])('opens original photos on demand and preserves selection, quantity and scroll after %s', async method => {
  await mount()
  expect(mocks.getItem).not.toHaveBeenCalled()
  expect(mocks.getItemPhotos).not.toHaveBeenCalled()
  const row = root.querySelector('.product-row')!
  const selected = root.querySelector<HTMLInputElement>('.product-check')!
  selected.checked = true; selected.dispatchEvent(new Event('change', { bubbles: true }))
  const quantity = root.querySelector<HTMLInputElement>('.product-actions input')!
  quantity.value = '3'; quantity.dispatchEvent(new Event('input', { bubbles: true })); await settle()
  root.scrollTop = 420
  const opener = photo()
  expect(opener.tagName).toBe('BUTTON')
  expect(opener.type).toBe('button')
  expect(opener.getAttribute('aria-label')).toBe(`Ver fotos de ${product.name}`)
  await openPhoto()
  expect(mocks.getItem).toHaveBeenCalledWith(product.id, expect.any(AbortSignal))
  expect(mocks.getItemPhotos).toHaveBeenCalledWith(product.id)
  expect(dialog()?.parentElement?.parentElement).toBe(document.body)
  expect(root.querySelector('.gallery-dialog')).toBeNull()
  expect(document.body.style.overflow).toBe('hidden')
  expect(dialog()?.querySelector('.gallery-main')?.getAttribute('src')).toBe('original-cover')
  dialog()!.querySelector<HTMLButtonElement>('[aria-label="Foto 2 do produto"]')!.click(); await settle()
  expect(dialog()?.querySelector('.gallery-main')?.getAttribute('src')).toBe('original-side')
  if (method === 'close') dialog()!.querySelector<HTMLButtonElement>('[data-dialog-close]')!.click()
  else if (method === 'backdrop') dialog()!.parentElement!.click()
  else dialog()!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
  await settle()
  expect(dialog()).toBeNull()
  expect(document.activeElement).toBe(opener)
  expect(document.body.style.overflow).toBe('auto')
  expect(root.querySelector('.product-row')).toBe(row)
  expect(selected.checked).toBe(true)
  expect(quantity.value).toBe('3')
  expect(root.scrollTop).toBe(420)
  expect(window.scrollTo).not.toHaveBeenCalled()
  expect(mocks.confirm).not.toHaveBeenCalled()
  expect(mocks.preview).not.toHaveBeenCalled()
  expect(document.querySelector('.replenishment-dialog')).toBeNull()
})

it('shows loading without locking scroll and suppresses focus refresh while opening or viewing a photo', async () => {
  const now = vi.spyOn(Date, 'now').mockReturnValue(100000)
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
  const loading = deferred<InventoryItem>()
  mocks.getItem.mockReturnValueOnce(loading.promise)
  await mount(); await openPhoto()
  expect(photo().getAttribute('aria-busy')).toBe('true')
  expect(root.querySelector('.product-identity [role="status"]')?.textContent).toBe('Abrindo foto…')
  expect(document.body.style.overflow).toBe('auto')
  now.mockReturnValue(140000); window.dispatchEvent(new Event('focus')); await settle()
  expect(mocks.list).toHaveBeenCalledTimes(1)
  loading.resolve(fullProduct); await settle()
  expect(dialog()).not.toBeNull()
  window.dispatchEvent(new Event('focus')); await settle()
  expect(mocks.list).toHaveBeenCalledTimes(1)
})

it('keeps the cover and close controls usable while extra photos load or fail', async () => {
  const photos = deferred<{ additional_images: string[] }>()
  mocks.getItemPhotos.mockReturnValueOnce(photos.promise)
  await mount(); await openPhoto()
  expect(dialog()?.textContent).toContain('Carregando fotos')
  dialog()!.querySelector<HTMLButtonElement>('[data-dialog-close]')!.click(); await settle()
  photos.resolve({ additional_images: ['late-side'] }); await settle()
  expect(dialog()).toBeNull()
  expect(document.body.style.overflow).toBe('auto')
  mocks.getItemPhotos.mockRejectedValueOnce(new Error('offline'))
  await openPhoto()
  expect(dialog()?.querySelector('[role="alert"]')).not.toBeNull()
  expect(dialog()?.querySelector('.gallery-main')?.getAttribute('src')).toBe('original-cover')
  dialog()!.querySelector<HTMLButtonElement>('[data-dialog-close]')!.click(); await settle()
  expect(dialog()).toBeNull()
})

it('keeps products without photos as non-interactive placeholders without fetching an original', async () => {
  mocks.list.mockResolvedValue({ items: [{ ...product, has_image: false }], total: 1, page: 1, page_size: 40 })
  await mount()
  expect(photo().disabled).toBe(true)
  expect(photo().getAttribute('aria-label')).toBe(`${product.name} está sem foto`)
  photo().click(); await settle()
  expect(mocks.getItem).not.toHaveBeenCalled()
  expect(dialog()).toBeNull()
})

it('reports a removed photo and fetch errors without replacing the product or invoking replenishment', async () => {
  mocks.getItem.mockRejectedValueOnce(new Error('offline'))
  await mount(); await openPhoto()
  expect(root.querySelector('.photo-error')?.textContent).toContain('Toque na miniatura para tentar novamente')
  expect(photo().getAttribute('aria-busy')).toBe('false')
  expect(document.body.style.overflow).toBe('auto')
  mocks.getItem.mockResolvedValueOnce({ ...fullProduct, image_data: null, has_image: false })
  await openPhoto()
  expect(root.querySelector('.photo-error')?.textContent).toBe('Este produto não tem foto disponível.')
  expect(dialog()).toBeNull()
  await openPhoto()
  expect(dialog()).not.toBeNull()
  expect(mocks.confirm).not.toHaveBeenCalled()
  expect(mocks.preview).not.toHaveBeenCalled()
})

it.each(['search', 'user', 'unmount'])('discards the pending original when %s changes the context', async reason => {
  const pending = deferred<InventoryItem>()
  mocks.getItem.mockReturnValueOnce(pending.promise)
  await mount(); await openPhoto()
  const signal = mocks.getItem.mock.calls[0][1] as AbortSignal
  if (reason === 'search') root.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
  else if (reason === 'user') mocks.auth.user.id = 'other-user'
  else { app!.unmount(); app = undefined }
  await settle()
  expect(signal.aborted).toBe(true)
  pending.resolve(fullProduct); await settle()
  expect(dialog()).toBeNull()
  expect(mocks.getItemPhotos).not.toHaveBeenCalled()
  expect(document.body.style.overflow).toBe('auto')
})

it('cancels a pending photo before recovering a saved confirmation and rejects the late response', async () => {
  const request = replenishmentRequest([{ ...product, copies: 1 }], 'saved-photo-qa')
  sessionStorage.setItem('eleven-replenishment-confirmation:owner', JSON.stringify(request))
  await mount()
  document.querySelector<HTMLButtonElement>('.replenishment-dialog [data-dialog-close]')!.click()
  await settle()
  const pending = deferred<InventoryItem>()
  mocks.getItem.mockReturnValueOnce(pending.promise)
  await openPhoto()
  const signal = mocks.getItem.mock.calls[0][1] as AbortSignal
  const recover = Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find(
    button => button.textContent?.trim() === 'Recuperar confirmação',
  )!
  recover.click(); await settle()
  expect(signal.aborted).toBe(true)
  expect(photo().getAttribute('aria-busy')).toBe('false')
  expect(document.querySelector('.replenishment-dialog')).not.toBeNull()
  pending.resolve(fullProduct); await settle()
  expect(dialog()).toBeNull()
  expect(document.querySelector('.replenishment-dialog')).not.toBeNull()
  expect(mocks.getItemPhotos).not.toHaveBeenCalled()
  expect(mocks.confirm).not.toHaveBeenCalled()
  expect(mocks.preview).not.toHaveBeenCalled()
  expect(JSON.parse(sessionStorage.getItem('eleven-replenishment-confirmation:owner')!)).toEqual(request)
})

it.each([
  ['es', 'Ver fotos de', 'Abriendo foto…'],
  ['en', 'View photos of', 'Opening photo…'],
])('provides accessible photo labels and loading text in %s', async (locale, label, loadingText) => {
  mocks.getItem.mockReturnValueOnce(new Promise(() => undefined))
  await mount(locale); await openPhoto()
  expect(photo().getAttribute('aria-label')).toBe(`${label} ${product.name}`)
  expect(root.querySelector('.product-identity [role="status"]')?.textContent).toBe(loadingText)
})
