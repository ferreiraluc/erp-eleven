import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import i18n from '@/i18n'
import SalesManagementView from './SalesManagementView.vue'
import type { ManagedSale } from '@/services/pdvManagement'

const mocks = vi.hoisted(() => ({ detail: vi.fn(), list: vi.fn(), options: vi.fn(), preview: vi.fn(), commit: vi.fn() }))
const receipts = vi.hoisted(() => ({ preview: vi.fn(), state: vi.fn(), print: vi.fn(), pdf: vi.fn() }))
vi.mock('@/services/pdvReceipts', () => ({ pdvReceipts: receipts }))
vi.mock('@/components/inventory/BarcodeScanner.vue', async () => {
  const { defineComponent, h } = await import('vue')
  return { default: defineComponent({ emits: ['barcode-detected', 'close'], setup(_, { emit }) {
    return () => h('button', { onClick: () => emit('barcode-detected', 'ABCDEF1234') }, 'fixture scan ticket')
  } }) }
})
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ isOwner: false, ownSales: true }) }))
vi.mock('@/services/pdvManagement', async original => ({ ...await original<object>(), pdvManagementAPI: mocks }))
vi.mock('@/services/api', () => ({ default: {}, inventoryAPI: {}, pdvAPI: {} }))

const sale = (id: string): ManagedSale => ({
  id, vendedor_id: 'seller', cliente_id: 'customer', cliente_nome: `Cliente ${id}`,
  subtotal_gs: '100', desconto_gs: '0', total_gs: '100', refunded_gs: '0', fiado_reversed_gs: '0',
  status: 'completed', stock_applied: true, notas: null, version: 1,
  created_at: '2026-10-14T14:00:00-03:00', deleted_at: null, seller: 'Vendedor', actor: 'Vendedor',
  can_manage: false, payments: [], events: [], items: [], payment_difference_gs: '0',
})
let app: App | undefined, container: HTMLElement, router: Router
const settle = async () => { for (let n = 0; n < 12; n++) { await nextTick(); await Promise.resolve() } }
async function mount(path: string) {
  router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/vendas-pdv', component: SalesManagementView }] })
  await router.push(path); await router.isReady()
  app = createApp(RouterView).use(router).use(i18n)
  app.mount(container); await settle()
}
function button(text: string) { return Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === text) }
beforeEach(() => {
  vi.resetAllMocks(); i18n.global.locale.value = 'pt'
  container = document.createElement('div'); document.body.append(container)
  mocks.list.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20, summary: { net_gs: '0', refunded_gs: '0', cancelled: 0 } })
  mocks.options.mockResolvedValue({ sellers: [] })
  mocks.detail.mockImplementation(async id => sale(id))
  receipts.state.mockResolvedValue({ printer: null, job: null })
  receipts.preview.mockResolvedValue({title:'ELEVEN',location:'Shopping Paris - PY',email:'contato@elevenparispy.com',
    code:'ABCDEF1234',sale_id:'older-sale',date:'14/10/2026 14:00',status:'Venta registrada',status_changed:false,copy:false,
    items:[],payments:[],subtotal:'G$ 100',total:'G$ 100',seller:'Lucas',customer:'Consumidor final',footer:['¡Gracias por su compra!'],barcode:'data:image/svg+xml;base64,'})
})
afterEach(() => { app?.unmount(); app = undefined; container.remove() })

describe('Customer-to-sale navigation', () => {
  it('lets an employee open and download their receipt without editing or dispatching a print', async () => {
    const createUrl = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:receipt')
    const clickLink = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    receipts.pdf.mockResolvedValue(new Blob(['%PDF-1.4'], { type:'application/pdf' }))
    try {
      await mount('/vendas-pdv?sale_id=older-sale')
      button('Ticket / PDF')!.click(); await settle()
      expect(document.querySelector('.receipt-paper')?.getAttribute('lang')).toBe('es')
      expect(document.querySelector('.receipt-paper')?.textContent).toContain('Shopping Paris - PY')
      expect(receipts.preview).toHaveBeenCalledWith('older-sale')
      expect(receipts.print).not.toHaveBeenCalled()
      button('📄 Salvar PDF')!.click(); await settle()
      expect(receipts.pdf).toHaveBeenCalledWith('older-sale'); expect(clickLink).toHaveBeenCalledTimes(1)
      expect(mocks.commit).not.toHaveBeenCalled(); expect(receipts.print).not.toHaveBeenCalled()
      document.querySelector<HTMLButtonElement>('.receipt-actions [data-dialog-close]')!.click(); await settle()
      expect(document.querySelector('.receipt-overlay')).toBeNull()
      expect((document.querySelector('.sale-overlay') as HTMLElement).style.display).not.toBe('none')
    } finally { createUrl.mockRestore(); clickLink.mockRestore() }
  })

  it('puts scanned ticket codes in the search and clears stale date filters', async () => {
    await mount('/vendas-pdv')
    const date = container.querySelector<HTMLInputElement>('input[type="date"]')!
    date.value = '2024-01-01'; date.dispatchEvent(new Event('input', { bubbles:true })); await settle()
    button('Ler ticket')!.click(); await settle(); button('fixture scan ticket')!.click(); await settle()
    expect(mocks.list).toHaveBeenLastCalledWith(expect.objectContaining({q:'ABCDEF1234',page:1}))
    expect(mocks.list.mock.calls.at(-1)![0]).not.toHaveProperty('date_from')
    expect(mocks.detail).not.toHaveBeenCalled(); expect(receipts.print).not.toHaveBeenCalled()
  })
  it('opens a linked sale outside the current page and retains employee permissions', async () => {
    await mount('/vendas-pdv?sale_id=older-sale&origin=customer')
    expect(mocks.detail).toHaveBeenCalledWith('older-sale')
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain('Cliente older-sale')
    expect(button('Editar venda')).toBeUndefined(); expect(button('Excluir venda')).toBeUndefined()
    button('Fechar')!.click(); await settle()
    expect(document.querySelector('[role="dialog"]')).toBeNull()
    await vi.waitFor(() => expect(router.currentRoute.value.query).toEqual({ origin: 'customer' }))
    expect(mocks.preview).not.toHaveBeenCalled(); expect(mocks.commit).not.toHaveBeenCalled()
  })

  it('surfaces denial from the detail API independently of the sales list and can retry', async () => {
    mocks.detail.mockRejectedValueOnce({ response: { status: 404, data: { detail: 'Venda não encontrada' } } })
    await mount('/vendas-pdv?sale_id=unavailable')
    expect(document.querySelector('[role="dialog"] [role="alert"]')?.textContent).toContain('Venda não encontrada')
    expect(container.querySelector('.sales-results')).not.toBeNull()
    expect(button('Editar venda')).toBeUndefined()
    button('Tentar novamente')!.click(); await settle()
    expect(mocks.detail).toHaveBeenCalledTimes(2)
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain('Cliente unavailable')
  })

  it('loads each route selection and discards details from the previous sale', async () => {
    let finish!: (value: ManagedSale) => void
    mocks.detail.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    await mount('/vendas-pdv?sale_id=old')
    await router.push('/vendas-pdv?sale_id=new'); await settle()
    expect(mocks.detail).toHaveBeenLastCalledWith('new')
    finish(sale('old')); await settle()
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain('Cliente new')
    expect(document.querySelector('[role="dialog"]')?.textContent).not.toContain('Cliente old')
    await router.push('/vendas-pdv'); await settle()
    expect(document.querySelector('[role="dialog"]')).toBeNull()
  })

  it('ignores ambiguous sale parameters rather than selecting a different sale', async () => {
    await mount('/vendas-pdv?sale_id=one&sale_id=two')
    expect(mocks.detail).not.toHaveBeenCalled()
    expect(document.querySelector('[role="dialog"]')).toBeNull()
  })
})
