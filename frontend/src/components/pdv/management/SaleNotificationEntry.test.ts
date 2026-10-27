import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import SalesManagementView from '@/views/SalesManagementView.vue'
import SaleManagerModal from './SaleManagerModal.vue'
const mock = vi.hoisted(() => ({ list: vi.fn(), options: vi.fn(), detail: vi.fn(), commit: vi.fn(), preview: vi.fn() }))
vi.mock('@/services/pdvManagement', () => ({ pdvManagementAPI: mock, saleError: () => 'Erro' }))
vi.mock('@/components/notifications/SaleNotificationModal.vue', () => ({ default: { props: ['saleId', 'itemId'], emits: ['close', 'sent'], template: '<div class="test-notification" :data-sale="saleId" :data-product="itemId"><button @click="$emit(\'close\')">Fechar aviso</button></div>' } }))
vi.mock('@/components/inventory/ProductThumbnail.vue', () => ({ default: { template: '<span />' } }))
vi.mock('@/components/inventory/BarcodeScanner.vue', () => ({ default: { template: '<span />' } }))
vi.mock('@/components/pdv/PDVReceiptModal.vue', () => ({ default: { template: '<span />' } }))
vi.mock('./SaleEditForm.vue', () => ({ default: { template: '<span />' } }))
const saleId = '11111111-1111-4111-8111-111111111111', itemId = '22222222-2222-4222-8222-222222222222'
const sale = () => ({ id: saleId, ticket_code: '8B316EBBCA', vendedor_id: 'seller', seller: 'Sol', created_at: '2026-10-26T13:00:00', status: 'completed', cliente_nome: 'Cliente', total_gs: '100000', subtotal_gs: '100000', refunded_gs: '0', desconto_gs: '0', deleted_at: null, can_manage: true, version: 1, actor: 'Sol', notas: null, payment_difference_gs: '0', payments: [], events: [], items: [{ id: 'line', item_id: itemId, item_name: 'Camiseta', item_size: 'L', item_color: 'Preto', quantity: 1, returned_quantity: 0, unit_price_gs: 100000, total_gs: 100000, discount_gs: 0, location: 'loja', is_avulso: false }] })
let app: App, root: HTMLElement, auth: ReturnType<typeof useAuthStore>
async function flush() { for (let i = 0; i < 8; i++) await nextTick() }
async function mount(detail = false, owner = true) {
  const pinia = createPinia(); setActivePinia(pinia); auth = useAuthStore()
  auth.user = { id: owner ? 'owner' : 'seller', nome: owner ? 'Lucas' : 'Sol', email: owner ? 'lucas@eleven.com' : 'sol@example.test', role: owner ? 'ADMIN' : 'VENDEDOR', sales_scope: owner ? 'all' : 'own' } as typeof auth.user
  auth.status = 'authenticated'; auth.token = 'test-session'
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/vendas-pdv', component: { template: '<div />' } }, { path: '/inventory', component: { template: '<div />' } }, { path: '/pdv', component: { template: '<div />' } }, { path: '/', component: { template: '<div />' } }] })
  await router.push('/vendas-pdv'); await router.isReady()
  root = document.createElement('div'); document.body.append(root)
  app = createApp(detail ? SaleManagerModal : SalesManagementView, detail ? { saleId, sellers: [{ id: 'seller', name: 'Sol' }] } : {}).use(pinia).use(router)
  app.mount(root); await flush()
}
function button(text: string) { const element = Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === text); if (!element) throw Error(`Missing ${text}`); return element }
beforeEach(() => {
  mock.detail.mockResolvedValue(sale()); mock.options.mockResolvedValue({ sellers: [{ id: 'seller', name: 'Sol' }] })
  mock.list.mockResolvedValue({ items: [{ ...sale(), items_count: 1, payment_methods: [] }], total: 1, page: 1, page_size: 20, own_sales_only: false, summary: { net_gs: '100000', refunded_gs: '0', cancelled: 0 } })
})
afterEach(() => { app?.unmount(); root?.remove(); vi.resetAllMocks() })
describe('Contextual notification entry points', () => {
  it('opens the owner composer directly from the sale list without sending or changing a sale', async () => {
    await mount(); button('Notificar vendedor').click(); await flush()
    expect(document.querySelector('.test-notification')?.getAttribute('data-sale')).toBe(saleId)
    expect(mock.commit).not.toHaveBeenCalled(); expect(mock.preview).not.toHaveBeenCalled()
    auth.user = { ...auth.user!, email: 'other@example.test' }; await flush()
    expect(document.querySelector('.test-notification')).toBeNull()
  })
  it('passes sale and inventory product identities from the detail and restores the parent on close', async () => {
    await mount(true); button('Notificar sobre produto').click(); await flush()
    expect(document.querySelector('.test-notification')?.getAttribute('data-sale')).toBe(saleId)
    expect(document.querySelector('.test-notification')?.getAttribute('data-product')).toBe(itemId)
    expect((document.querySelector('.sale-overlay') as HTMLElement).style.display).toBe('none')
    button('Fechar aviso').click(); await flush()
    expect(document.querySelector('.test-notification')).toBeNull()
    expect((document.querySelector('.sale-overlay') as HTMLElement).style.display).not.toBe('none')
    expect(document.querySelector('a[href*="item_id="]')?.getAttribute('href')).toBe(`/inventory?item_id=${itemId}`)
    expect(mock.commit).not.toHaveBeenCalled()
  })
  it('does not expose sending controls to a salesperson or offer a link for an unlinked product', async () => {
    mock.detail.mockResolvedValue({ ...sale(), items: [{ ...sale().items[0], item_id: null, is_avulso: true }] })
    await mount(true, false)
    expect(document.body.textContent).not.toContain('Notificar vendedor')
    expect(document.body.textContent).not.toContain('Notificar sobre produto')
    expect(document.querySelector('a[href*="item_id="]')).toBeNull()
  })
})
