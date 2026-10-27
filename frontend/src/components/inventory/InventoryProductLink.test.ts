import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { createI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import InventoryProductLink from './InventoryProductLink.vue'

const mock = vi.hoisted(() => ({ getItem: vi.fn(), getItemPhotos: vi.fn() }))
vi.mock('@/services/api', () => ({ inventoryAPI: mock, authAPI: {} }))
vi.mock('./ProductGallery.vue', () => ({ default: { props: ['additional'], template: '<div class="test-gallery">{{ additional }}</div>' } }))
const first = '11111111-1111-4111-8111-111111111111', second = '22222222-2222-4222-8222-222222222222'
const product = (id = first) => ({ id, name: id === first ? 'Camiseta Boss' : 'Calça Armani', inventory_code: 'INV-ABC123', sku_internal: 'LEGACY-001', description: 'Placa de metal', brand: 'Boss', category: 'Camisetas', size: 'L', color: 'Preto', sale_price: 72, sale_currency: 'USD', is_active: true, stock_loja: 0, stock_deposito: null, current_stock: null })
let app: App, root: HTMLElement, router: Router, auth: ReturnType<typeof useAuthStore>
async function flush() { for (let i = 0; i < 6; i++) await nextTick() }
async function mount(query = `item_id=${first}&status=low`) {
  const pinia = createPinia(); setActivePinia(pinia); auth = useAuthStore()
  auth.user = { id: 'seller', nome: 'Sol', email: 'sol@example.test', role: 'VENDEDOR', sales_scope: 'own' } as typeof auth.user
  auth.token = 'test-session'; auth.status = 'authenticated'
  router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/inventory', component: { template: '<div />' } }] })
  await router.push(`/inventory?${query}`); await router.isReady()
  root = document.createElement('div'); document.body.append(root)
  app = createApp(InventoryProductLink).use(pinia).use(router).use(createI18n({ legacy: false, locale: 'pt', messages: { pt: {} } }))
  app.mount(root); await flush()
}
beforeEach(() => { mock.getItem.mockImplementation(async id => product(id)); mock.getItemPhotos.mockResolvedValue({ additional_images: [] }) })
afterEach(() => { app?.unmount(); root?.remove(); vi.resetAllMocks() })
describe('Product notification destination', () => {
  it('opens the exact product without changing inventory filters and keeps unknown stock distinct from zero', async () => {
    await mount()
    expect(mock.getItem).toHaveBeenCalledWith(first, expect.any(AbortSignal))
    expect(document.body.textContent).toContain('Camiseta Boss')
    expect(document.body.textContent).toContain('Placa de metal')
    const balances = Array.from(document.querySelectorAll('.product-details div')).map(e => e.textContent)
    expect(balances).toContain('Loja0'); expect(balances).toContain('Depósito—')
    expect(router.currentRoute.value.query.status).toBe('low')
    expect(document.querySelectorAll('input,textarea,select')).toHaveLength(0)
    ;(document.querySelector('[data-dialog-close]') as HTMLButtonElement).click(); await flush()
    await vi.waitFor(() => expect(router.currentRoute.value.query).toEqual({ status: 'low' }))
    expect(document.querySelector('.product-link-dialog')).toBeNull()
    expect(document.body.style.overflow).not.toBe('hidden')
  })
  it('does not request an invalid or repeated URL identifier', async () => {
    await mount('item_id=wrong')
    expect(mock.getItem).not.toHaveBeenCalled(); expect(document.body.textContent).toContain('O link do produto é inválido.')
    await router.push(`/inventory?item_id=${first}&item_id=${second}`); await flush()
    expect(mock.getItem).not.toHaveBeenCalled()
  })
  it('aborts an old request and discards stale product and gallery responses after navigation', async () => {
    let resolve!: (value: ReturnType<typeof product>) => void
    mock.getItem.mockReturnValueOnce(new Promise(r => { resolve = r }))
    await mount(); const signal = mock.getItem.mock.calls[0][1]
    await router.push(`/inventory?item_id=${second}`); await flush()
    resolve(product()); await flush()
    expect(signal.aborted).toBe(true); expect(document.body.textContent).toContain('Calça Armani')
    expect(document.body.textContent).not.toContain('Camiseta Boss')
    let photos!: (value: { additional_images: string[] }) => void
    mock.getItemPhotos.mockReturnValueOnce(new Promise(r => { photos = r }))
    await router.push(`/inventory?item_id=${first}`); await flush()
    await router.push(`/inventory?item_id=${second}`); await flush()
    photos({ additional_images: ['STALE_IMAGE'] }); await flush()
    expect(document.body.textContent).not.toContain('STALE_IMAGE')
  })
  it('clears private product data on logout and ignores a pending response', async () => {
    let resolve!: (value: ReturnType<typeof product>) => void
    mock.getItem.mockReturnValueOnce(new Promise(r => { resolve = r }))
    await mount(); auth.expire(); await flush(); resolve(product()); await flush()
    expect(document.querySelector('.product-link-dialog')).toBeNull()
    expect(document.body.textContent).not.toContain('Camiseta Boss')
    expect(document.body.style.overflow).not.toBe('hidden')
  })
  it('shows an unavailable product honestly and permits a retry without displaying a cached product', async () => {
    mock.getItem.mockRejectedValueOnce({ response: { status: 404 } }); await mount()
    expect(document.querySelector('[role=alert]')?.textContent).toContain('Este produto não está disponível para sua conta.')
    expect(document.body.textContent).not.toContain('Camiseta Boss')
    ;(Array.from(document.querySelectorAll('button')).find(b => b.textContent === 'Tentar novamente') as HTMLButtonElement).click(); await flush()
    expect(document.body.textContent).toContain('Camiseta Boss')
  })
})
