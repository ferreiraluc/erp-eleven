import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import MacTicketSetup from './MacTicketSetup.vue'
const api=vi.hoisted(()=>({destinations:vi.fn(),prepareMac:vi.fn(),testPrinter:vi.fn(),activatePrinter:vi.fn(),credential:vi.fn()}))
vi.mock('@/services/pdvReceipts',()=>({pdvReceipts:api}))
let app:App, root:HTMLDivElement
const tick=async()=>{for(let i=0;i<6;i++)await Promise.resolve();await nextTick()}
afterEach(()=>{app?.unmount();root?.remove();vi.resetAllMocks()})
const mac={id:'mac',name:'3nStar',driver:'escpos_tcp',paper_width_mm:80,paper_height_mm:0,auto_receipts:false,last_seen_at:'2026-10-20T12:00:00Z',last_test:null}
const response=(devices:object[])=>({devices,mac_package_url:'https://example.invalid/agent.zip',mac_agent_version:'test'})
const button=(text:string)=>Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find(b=>b.textContent?.includes(text))!
async function mount(devices:object[]) {
  api.destinations.mockResolvedValue(response(devices))
  root=document.createElement('div');document.body.append(root)
  app=createApp(MacTicketSetup);app.mount(root);await tick()
}
describe('staged Mac printer',()=>{
  it('opens read-only and preparing does not activate or print',async()=>{
    await mount([])
    expect(api.prepareMac).not.toHaveBeenCalled()
    expect(api.testPrinter).not.toHaveBeenCalled()
    api.prepareMac.mockResolvedValue({device:mac,token:'synthetic-only'})
    api.destinations.mockResolvedValue(response([mac]))
    button('Preparar 3nStar').click();await tick()
    expect(root.textContent).toContain('Credencial exclusiva do Mac')
    expect(api.activatePrinter).not.toHaveBeenCalled()
    expect(api.testPrinter).not.toHaveBeenCalled()
    expect(button('Ativar 3nStar').disabled).toBe(true)
  })
  it('requires submitted test and physical confirmation before activating',async()=>{
    await mount([{...mac,last_test:{id:'test',status:'claimed',diagnostic_message:null}}])
    expect(button('Ativar 3nStar').disabled).toBe(true)
    expect(button('Imprimir teste').disabled).toBe(true)
    api.destinations.mockResolvedValue(response([{...mac,last_test:{id:'test',status:'submitted',diagnostic_message:null}}]))
    button('Atualizar estado').click();await tick()
    expect(api.testPrinter).not.toHaveBeenCalled()
    expect(button('Ativar 3nStar').disabled).toBe(true)
    const check=root.querySelector<HTMLInputElement>('input[type=checkbox]')!
    check.checked=true;check.dispatchEvent(new Event('change'));await tick()
    api.activatePrinter.mockResolvedValue({device:{...mac,auto_receipts:true}})
    button('Ativar 3nStar').click();await tick()
    expect(api.activatePrinter).toHaveBeenCalledWith('mac','test')
  })
  it('preserves test request identity across a lost response',async()=>{
    await mount([mac])
    api.testPrinter.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({job:{id:'test',status:'pending'}})
    button('Imprimir teste').click();await tick()
    const key=api.testPrinter.mock.calls[0][1]
    button('Imprimir teste').click();await tick()
    expect(api.testPrinter.mock.calls[1]).toEqual(['mac',key])
    expect(button('Imprimir teste').disabled).toBe(true)
    expect(api.activatePrinter).not.toHaveBeenCalled()
  })
})
