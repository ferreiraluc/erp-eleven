import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import PDVReceiptDelivery from './PDVReceiptDelivery.vue'
const api = vi.hoisted(() => ({state:vi.fn(),print:vi.fn()}))
vi.mock('@/services/pdvReceipts',()=>({pdvReceipts:api}))
const fixture = {printer:{id:'z',name:'Zebra ZD220'},job:{id:'j',status:'pending',diagnostic_message:null}}
let app: App, root: HTMLDivElement
const tick=async()=>{await Promise.resolve();await Promise.resolve();await nextTick()}
function click(label:string){const button=Array.from(root.querySelectorAll('button')).find(b=>b.textContent?.includes(label));expect(button).toBeTruthy();button!.click()}
beforeEach(()=>{api.state.mockResolvedValue(fixture);root=document.createElement('div');document.body.append(root)})
afterEach(()=>{app?.unmount();root.remove();vi.resetAllMocks()})
async function mount(){app=createApp(PDVReceiptDelivery,{saleId:'sale'});app.mount(root);await tick()}
describe('ticket delivery',()=>{
  it('opening a committed receipt only reads status and never dispatches another print',async()=>{
    await mount();expect(root.textContent).toContain('Na fila do caixa');expect(api.print).not.toHaveBeenCalled()
    click('Atualizar estado');await tick();expect(api.state).toHaveBeenCalledTimes(2);expect(api.print).not.toHaveBeenCalled()
    expect(root.textContent).not.toContain('Outra cópia')
  })
  it('an uncertain result requires a separate confirmation, and a failed response reuses its copy key',async()=>{
    api.state.mockResolvedValue({...fixture,job:{...fixture.job,status:'uncertain'}})
    api.print.mockRejectedValueOnce(new Error('timeout')).mockResolvedValue({...fixture,job:{...fixture.job,id:'copy'}})
    await mount();click('Outra cópia');await tick();expect(api.print).not.toHaveBeenCalled()
    click('Confirmar nova cópia');await tick();const key=api.print.mock.calls[0][1];expect(key).toBeTruthy()
    click('Confirmar nova cópia');await tick();expect(api.print.mock.calls[1]).toEqual(['sale',key]);expect(root.textContent).toContain('Na fila do caixa')
  })
  it('missing printer remains a visible fallback without dispatch',async()=>{
    api.state.mockResolvedValue({printer:null,job:null});await mount()
    expect(root.textContent).toContain('não ativada');expect(api.print).not.toHaveBeenCalled()
  })
})
