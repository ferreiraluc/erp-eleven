import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import ProductHistoryModal from './ProductHistoryModal.vue'
import ItemFormModal from './ItemFormModal.vue'
import type { ProductHistory, HistorySection } from '@/services/inventoryHistory'
const mock = vi.hoisted(() => ({ get: vi.fn(), preview: vi.fn() }))
vi.mock('@/services/inventoryHistory', () => ({ inventoryHistoryAPI: mock }))
vi.mock('@/services/inventoryDeletion', () => ({ inventoryDeletionAPI: mock }))
vi.mock('@/services/api', () => ({ inventoryAPI: {}, ocrAPI: {} }))
let app: App, root: HTMLDivElement
const product = { id:'product',name:'Polo',sku_internal:'LOCAL-001',barcode:'123',brand:'Marca',size:'P',color:'Branco',category:'Camisetas',is_active:true,created_at:'2026-10-07T12:00:00-03:00',updated_at:null,created_by:'Lucas',current_stock:0,stock_loja:0,stock_deposito:null }
const fixture = (section: HistorySection = 'movements'): ProductHistory => ({ product,section,page:1,page_size:20,total:0,totals:{movements:0,sales:0,counts:0,changes:0},rows:[],own_sales_only:false,can_view_changes:true })
const buttons = (name: string) => Array.from(document.querySelectorAll('button')).filter(b => b.textContent?.trim() === name)
async function click(name: string) { const b=buttons(name)[0]; if(!b)throw Error(`Missing ${name}`); b.click(); await flush() }
async function flush() { await nextTick(); await nextTick(); await nextTick() }
async function mount(form = false) {
  root=document.createElement('div');document.body.append(root)
  const i18n=createI18n({legacy:false,locale:'pt',messages:{pt:{},es:{},en:{}}})
  app=createApp(form ? ItemFormModal : ProductHistoryModal, form ? {item:product,canDeletePermanently:true} : {itemId:'product'}).use(i18n)
  app.mount(root);await flush();return i18n
}
beforeEach(() => { mock.get.mockImplementation(async (_id,section) => fixture(section)) })
afterEach(() => { app?.unmount();root?.remove();vi.resetAllMocks() })
describe('Product history', () => {
  it('shows creation, unknown stock and known zero distinctly, with translated tabs', async () => {
    const i18n=await mount()
    expect(document.body.textContent).toContain('Lucas');expect(document.body.textContent).toContain('Não informado')
    expect(document.querySelector('.history-stock dd')?.textContent).toBe('0')
    expect(document.body.textContent).toContain('Nenhum registro nesta seção.')
    i18n.global.locale.value='es';await flush();expect(document.body.textContent).toContain('Historial del producto')
    i18n.global.locale.value='en';await flush();expect(document.body.textContent).toContain('Product history')
  })
  it('keeps personal sales private and does not turn a failed request into zero records', async () => {
    mock.get.mockResolvedValue({...fixture(),own_sales_only:true,can_view_changes:false,totals:{movements:0,sales:0,counts:0,changes:null}})
    await mount();expect(document.body.textContent).not.toContain('Alterações')
    mock.get.mockRejectedValueOnce(new Error('offline'))
    await click('Vendas0');expect(document.body.textContent).toContain('Você vê apenas suas próprias vendas.')
    expect(document.querySelector('[role=alert]')).not.toBeNull();expect(document.querySelector('.history-empty')).toBeNull()
    await click('Tentar novamente');expect(document.querySelector('[role=alert]')).toBeNull()
  })
  it('opens the relevant history from a blocked deletion, preserving the product form', async () => {
    mock.preview.mockResolvedValue({ item:product,allowed:false,blockers:[{code:'sales',count:2}],movement_count:1,plan_token:null })
    await mount(true);await click('Excluir definitivamente');await click('Ver histórico e vínculos')
    expect(mock.get).toHaveBeenLastCalledWith('product','sales',1)
    expect(document.querySelector('.history-dialog')).not.toBeNull()
    const close=document.querySelector('.history-dialog footer button:last-child') as HTMLButtonElement
    close.click();await flush()
    expect(document.querySelector('.history-dialog')).toBeNull();expect(document.querySelector('.modal-overlay')?.getAttribute('style')).not.toContain('display: none')
    expect(document.activeElement?.textContent).toBe('Histórico')
  })
  it('discards a stale response when the section changes', async () => {
    let resolve!: (data: ProductHistory) => void
    mock.get.mockReturnValueOnce(new Promise<ProductHistory>(r=>{resolve=r}))
    await mount();await click('Vendas')
    resolve({...fixture(),rows:[{kind:'movements',id:'old',at:null,actor:null,type:'entry',quantity:1,before:0,after:1,location_from:null,location_to:null,reason:'STALE',notes:null,reference_type:null,reference_id:null,restricted:false}]});await flush()
    expect(document.body.textContent).not.toContain('STALE')
    expect(document.querySelector('.history-tabs .active')?.textContent).toContain('Vendas')
  })
})
