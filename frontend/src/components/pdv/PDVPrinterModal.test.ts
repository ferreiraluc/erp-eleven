import { chooseDropdown, openDropdown } from '@/test/dropdown'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import PDVPrinterModal from './PDVPrinterModal.vue'
const api = vi.hoisted(() => ({ printer:vi.fn(), configure:vi.fn() }))
vi.mock('@/services/pdvReceipts', () => ({ pdvReceipts:api }))
vi.mock('@/directives/erpDialog', () => ({ vErpDialog:{} }))
let app:App, root:HTMLDivElement
const tick = async () => { await Promise.resolve(); await Promise.resolve(); await nextTick() }
afterEach(() => { app?.unmount(); root?.remove(); vi.resetAllMocks() })
async function mount(device:object|null) {
  api.printer.mockResolvedValue({device})
  api.configure.mockImplementation(async data => ({device:data,token:null}))
  root=document.createElement('div'); document.body.append(root)
  app=createApp(PDVPrinterModal); app.mount(root); await tick()
}
const form=()=>document.querySelector<HTMLFormElement>('.printer-dialog')!
async function submit() { form().dispatchEvent(new Event('submit',{cancelable:true})); await tick() }
describe('receipt media', () => {
  it('new installation defaults to 80 mm continuous and does not auto-enable or print', async () => {
    await mount(null)
    expect(form().textContent).toContain('Altura automática')
    expect(form().querySelectorAll('input[type=number]')).toHaveLength(1)
    expect(api.configure).not.toHaveBeenCalled()
    await submit()
    expect(api.configure).toHaveBeenCalledWith({name:'Zebra ZD220',paper_width_mm:80,paper_height_mm:0,auto_receipts:false})
  })
  it('keeps existing labels until continuous is selected and preserves its fixed height when switching back',async () => {
    await mount({id:'z',name:'Zebra',paper_width_mm:80,paper_height_mm:80,auto_receipts:true})
    const select=form().querySelector('.erp-dropdown')!
    expect((await openDropdown(select)).find(o => o.getAttribute('aria-selected') === 'true')?.value).toBe('labels')
    await chooseDropdown(select, 'continuous'); await tick(); await submit()
    expect(api.configure).toHaveBeenLastCalledWith({name:'Zebra',paper_width_mm:80,paper_height_mm:0,auto_receipts:true})
    await chooseDropdown(select, 'labels'); await tick(); await submit()
    expect(api.configure).toHaveBeenLastCalledWith({name:'Zebra',paper_width_mm:80,paper_height_mm:80,auto_receipts:true})
  })
})
