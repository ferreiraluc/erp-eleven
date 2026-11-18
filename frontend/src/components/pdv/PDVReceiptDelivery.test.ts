import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, reactive, type App } from 'vue'
import PDVReceiptDelivery from './PDVReceiptDelivery.vue'
const api = vi.hoisted(() => ({state:vi.fn(),print:vi.fn(),token:'fixture-session'}))
vi.mock('@/services/pdvReceipts',()=>({pdvReceipts:api}))
vi.mock('@/services/sessionStorage',()=>({storedToken:()=>api.token}))
const fixture = {printer:{id:'mac',name:'3nStar RPT006W'},job:{id:'j',status:'pending',diagnostic_message:null}}
const status=(value:string,id='j')=>({...fixture,job:{...fixture.job,id,status:value}})
let app: App | undefined, root: HTMLDivElement, props: {saleId:string}, hidden=false, online=true
const tick=async()=>{for(let n=0;n<6;n++)await Promise.resolve();await nextTick()}
const advance=async(ms:number)=>{await vi.advanceTimersByTimeAsync(ms);await tick()}
const button=(label:string)=>Array.from(root.querySelectorAll('button')).find(b=>b.textContent?.includes(label))
function click(label:string){expect(button(label)).toBeTruthy();button(label)!.click()}
function deferred<T>(){let resolve!:(value:T)=>void;const promise=new Promise<T>(r=>{resolve=r});return{promise,resolve}}
function visibility(value:boolean){hidden=value;document.dispatchEvent(new Event('visibilitychange'))}
function connection(value:boolean){online=value;window.dispatchEvent(new Event(value?'online':'offline'))}
beforeEach(()=>{
  vi.useFakeTimers();hidden=false;online=true;api.token='fixture-session'
  vi.spyOn(document,'hidden','get').mockImplementation(()=>hidden)
  vi.spyOn(navigator,'onLine','get').mockImplementation(()=>online)
  api.state.mockResolvedValue(fixture);props=reactive({saleId:'sale'})
  root=document.createElement('div');document.body.append(root)
})
afterEach(()=>{app?.unmount();app=undefined;root.remove();vi.clearAllTimers();vi.useRealTimers();vi.resetAllMocks()})
async function mount(){app=createApp({setup:()=>()=>h(PDVReceiptDelivery,{saleId:props.saleId})});app.mount(root);await tick()}
describe('ticket delivery',()=>{
  it.each(['pending','claimed'])('keeps Another copy visible and disabled while %s without dispatching a print',async jobStatus=>{
    api.state.mockResolvedValue(status(jobStatus));await mount()
    expect(button('Outra cópia')?.disabled).toBe(true)
    const hint=root.querySelector('.delivery-hint')!
    expect(hint.textContent).toContain('Para evitar impressões duplicadas')
    expect(button('Outra cópia')?.getAttribute('aria-describedby')).toBe(hint.id)
    click('Outra cópia');expect(button('Confirmar nova cópia')).toBeUndefined()
    click('Atualizar estado');await tick();expect(api.state).toHaveBeenCalledTimes(2)
    expect(api.print).not.toHaveBeenCalled()
  })
  it('polls pending and claimed through submitted then stops without automatically printing',async()=>{
    api.state.mockResolvedValueOnce(fixture).mockResolvedValueOnce(status('claimed')).mockResolvedValue(status('submitted'))
    await mount();await advance(2999);expect(api.state).toHaveBeenCalledOnce()
    await advance(1);expect(root.textContent).toContain('O agente está processando')
    expect(button('Outra cópia')?.disabled).toBe(true)
    await advance(3000);expect(root.textContent).toContain('Enviado à impressora. Confira a saída do papel.')
    expect(button('Outra cópia')?.disabled).toBe(false)
    await advance(60000);expect(api.state).toHaveBeenCalledTimes(3);expect(api.print).not.toHaveBeenCalled()
  })
  it('backs off failed reads, preserves visible status and blocks copies until a successful retry',async()=>{
    api.state.mockResolvedValueOnce(fixture).mockRejectedValueOnce(new Error('network')).mockRejectedValueOnce(new Error('network')).mockResolvedValue(status('submitted'))
    await mount();await advance(3000)
    expect(root.textContent).toContain('Na fila do caixa');expect(button('Outra cópia')?.disabled).toBe(true)
    await advance(5999);expect(api.state).toHaveBeenCalledTimes(2)
    await advance(1);expect(api.state).toHaveBeenCalledTimes(3)
    await advance(11999);expect(api.state).toHaveBeenCalledTimes(3)
    await advance(1);expect(api.state).toHaveBeenCalledTimes(4)
    expect(button('Outra cópia')?.disabled).toBe(false);expect(root.querySelector('[role=alert]')).toBeNull()
    expect(api.print).not.toHaveBeenCalled()
  })
  it('lets the operator retry an initial failure without waiting for backoff',async()=>{
    api.state.mockRejectedValueOnce(new Error('network')).mockResolvedValue(status('submitted'))
    await mount();expect(root.querySelector('[role=alert]')).not.toBeNull()
    click('Tentar novamente');await tick();expect(button('Outra cópia')?.disabled).toBe(false)
    await advance(60000);expect(api.state).toHaveBeenCalledTimes(2);expect(api.print).not.toHaveBeenCalled()
  })
  it('never offers another print using a stale terminal state after a failed refresh',async()=>{
    api.state.mockResolvedValueOnce(status('submitted')).mockRejectedValueOnce(new Error('network')).mockResolvedValue(status('submitted'))
    await mount();click('Atualizar estado');await tick();expect(button('Outra cópia')?.disabled).toBe(true)
    click('Outra cópia');expect(button('Confirmar nova cópia')).toBeUndefined()
    click('Tentar novamente');await tick();expect(button('Outra cópia')?.disabled).toBe(false)
    expect(api.print).not.toHaveBeenCalled()
  })
  it('pauses hidden/offline, rechecks on return and never overlaps reads',async()=>{
    const pending=deferred<typeof fixture>()
    await mount();visibility(true);await advance(10000);expect(api.state).toHaveBeenCalledOnce()
    api.state.mockReturnValueOnce(pending.promise)
    visibility(false);await tick();expect(api.state).toHaveBeenCalledTimes(2)
    window.dispatchEvent(new Event('online'));await advance(10000);expect(api.state).toHaveBeenCalledTimes(2)
    pending.resolve(fixture);await tick();connection(false);await advance(10000)
    expect(api.state).toHaveBeenCalledTimes(2);expect(button('Outra cópia')?.disabled).toBe(true)
    api.state.mockResolvedValue(status('submitted'));connection(true);await tick()
    expect(api.state).toHaveBeenCalledTimes(3);expect(button('Outra cópia')?.disabled).toBe(false)
    expect(api.print).not.toHaveBeenCalled()
  })
  it.each(['focus','erp:native-app-active'])('refreshes pending status on %s and removes its listener on close',async event=>{
    api.state.mockResolvedValueOnce(fixture).mockResolvedValue(status('submitted'))
    await mount();window.dispatchEvent(new Event(event));await tick()
    expect(api.state).toHaveBeenCalledTimes(2);expect(button('Outra cópia')?.disabled).toBe(false)
    app!.unmount();app=undefined;window.dispatchEvent(new Event(event));await advance(60000)
    expect(api.state).toHaveBeenCalledTimes(2);expect(api.print).not.toHaveBeenCalled()
  })
  it('does not start polling when the modal first mounts in the background',async()=>{
    hidden=true;await mount();await advance(60000);expect(api.state).not.toHaveBeenCalled()
    visibility(false);await tick();expect(api.state).toHaveBeenCalledOnce();expect(api.print).not.toHaveBeenCalled()
  })
  it('preserves a lost POST key through cancel and GET pending/submitted, explicitly reconciling before a new copy',async()=>{
    api.state.mockResolvedValueOnce(status('uncertain')).mockResolvedValueOnce(status('pending','copy')).mockResolvedValue(status('submitted','copy'))
    api.print.mockRejectedValueOnce(new Error('timeout')).mockResolvedValue(status('submitted','copy'))
    await mount();click('Outra cópia');await tick();expect(api.print).not.toHaveBeenCalled()
    expect(root.textContent).toContain('fila da impressora');expect(root.textContent).not.toContain('Windows')
    click('Confirmar nova cópia');await tick();const key=api.print.mock.calls[0][1];expect(key).toBeTruthy()
    expect(button('Retomar solicitação anterior')?.disabled).toBe(true)
    click('Cancelar');await tick();expect(button('Retomar solicitação anterior')?.disabled).toBe(true)
    await advance(6000);expect(button('Retomar solicitação anterior')?.disabled).toBe(true)
    await advance(3000);expect(button('Retomar solicitação anterior')?.disabled).toBe(false)
    expect(api.print).toHaveBeenCalledOnce()
    click('Retomar solicitação anterior');await tick()
    expect(root.textContent).toContain('Retome a mesma solicitação')
    expect(button('Confirmar nova cópia')).toBeUndefined()
    click('Retomar solicitação anterior');await tick();expect(api.print.mock.calls[1]).toEqual(['sale',key])
    click('Outra cópia');await tick();click('Confirmar nova cópia');await tick()
    expect(api.print.mock.calls[2][1]).not.toBe(key)
  })
  it('stops timers and ignores pending reads after the modal closes',async()=>{
    const pending=deferred<typeof fixture>()
    api.state.mockResolvedValueOnce(fixture).mockReturnValueOnce(pending.promise)
    await mount();await advance(3000);expect(api.state).toHaveBeenCalledTimes(2)
    app!.unmount();app=undefined;pending.resolve(fixture);await tick()
    visibility(false);connection(true);await advance(60000)
    expect(api.state).toHaveBeenCalledTimes(2);expect(api.print).not.toHaveBeenCalled();expect(vi.getTimerCount()).toBe(0)
  })
  it('discards old sale reads and never applies their loading state to the new sale',async()=>{
    const old=deferred<typeof fixture>(),current=deferred<typeof fixture>()
    api.state.mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise)
    await mount();props.saleId='sale-2';await tick();expect(api.state.mock.calls).toEqual([['sale'],['sale-2']])
    old.resolve(status('submitted','old'));await tick()
    expect(root.textContent).toContain('Consultando impressora');expect(button('Outra cópia')).toBeUndefined()
    current.resolve(status('claimed','current'));await tick()
    expect(root.textContent).toContain('O agente está processando');expect(button('Outra cópia')?.disabled).toBe(true)
  })
  it('discards a delayed print response and its copy key when switching sales',async()=>{
    const pending=deferred<typeof fixture>()
    api.state.mockResolvedValue(status('submitted'));api.print.mockReturnValueOnce(pending.promise).mockResolvedValue(status('pending','copy-2'))
    await mount();click('Outra cópia');await tick();click('Confirmar nova cópia');await tick()
    const oldKey=api.print.mock.calls[0][1]
    props.saleId='sale-2';await tick();pending.resolve(status('pending','old-copy'));await tick()
    expect(button('Outra cópia')?.disabled).toBe(false)
    click('Outra cópia');await tick();click('Confirmar nova cópia');await tick()
    expect(api.print.mock.calls[1][0]).toBe('sale-2');expect(api.print.mock.calls[1][1]).not.toBe(oldKey)
  })
  it.each([401,403,404])('stops retries and disables printing after HTTP %s',async httpStatus=>{
    api.state.mockResolvedValueOnce(fixture).mockRejectedValue({response:{status:httpStatus,data:{detail:'Forbidden fixture'}}})
    await mount();await advance(3000);await advance(60000)
    expect(api.state).toHaveBeenCalledTimes(2);expect(button('Outra cópia')).toBeUndefined()
    expect(button('Tentar novamente')).toBeUndefined();expect(api.print).not.toHaveBeenCalled()
  })
  it('ignores a delayed response and stops polling after the token changes',async()=>{
    const pending=deferred<typeof fixture>()
    api.state.mockReturnValueOnce(pending.promise)
    await mount();api.token='another-session';pending.resolve(status('submitted'));await tick()
    expect(root.textContent).toContain('Reabra o ticket');expect(button('Outra cópia')).toBeUndefined()
    await advance(60000);connection(true);await tick();expect(api.state).toHaveBeenCalledOnce();expect(api.print).not.toHaveBeenCalled()
  })
  it('clears receipt state immediately on session expiry and does not resume for another sale',async()=>{
    await mount();window.dispatchEvent(new Event('erp:session-expired'));await tick()
    expect(root.textContent).toContain('Reabra o ticket');expect(button('Outra cópia')).toBeUndefined()
    props.saleId='other';await tick();await advance(60000);expect(api.state).toHaveBeenCalledOnce();expect(api.print).not.toHaveBeenCalled()
  })
  it('unknown status remains blocked and is never described as ready to print',async()=>{
    api.state.mockResolvedValue(status('new-server-status'));await mount()
    expect(root.textContent).toContain('Aguardando confirmação');expect(root.textContent).not.toContain('Pronto para enviar')
    expect(button('Outra cópia')?.disabled).toBe(true);expect(api.print).not.toHaveBeenCalled()
  })
  it('missing printer remains a visible fallback without polling or dispatch',async()=>{
    api.state.mockResolvedValue({printer:null,job:null});await mount()
    expect(root.textContent).toContain('não ativada');await advance(60000)
    expect(api.state).toHaveBeenCalledOnce();expect(api.print).not.toHaveBeenCalled()
  })
})
