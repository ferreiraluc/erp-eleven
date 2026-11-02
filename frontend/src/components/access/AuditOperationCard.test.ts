import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import AuditOperationCard from './AuditOperationCard.vue'
import type { AuditEvent, AuditGroup } from '@/services/access'
import pt from '@/locales/pt.json'

const api=vi.hoisted(()=>({auditGroup:vi.fn()}))
vi.mock('@/services/access',()=>({accessAPI:api}))
let app:App,root:HTMLDivElement
const first:AuditEvent={id:'event1',occurred_at:'2026-11-01T15:00:00',user_id:'employee',actor_name:'Alejandro',source:'web',action:'create',entity:'stock_movements',entity_id:'movement1',module:'inventory',request_id:'request1',route:null,method:null,status_code:null,changes:{quantity_before:{before:null,after:5},quantity_after:{before:null,after:3},_context:{product:{name:'Camiseta azul',code:'INV-ABC12'},movement:{quantity_before:5,quantity_after:3,location_from:'loja'}}}}
const group={key:'pdv_sale:abc',kind:'sale',sale_id:'abc',sale_code:'ABCD123456',event_count:2,first_at:first.occurred_at,last_at:first.occurred_at,module:'pdv',actor_name:'Alejandro',actor_count:1,samples:[first]} satisfies AuditGroup
const filters={days:7,user_id:'employee',module:'inventory',action:'create'}
function mount(){root=document.createElement('div');document.body.append(root);app=createApp(AuditOperationCard,{group,filters}).use(createI18n({legacy:false,locale:'pt',messages:{pt}}));app.component('router-link',{props:['to'],template:'<a :data-target="JSON.stringify(to)"><slot /></a>'});app.mount(root)}
async function expand(){const details=root.querySelector('details')!;details.open=true;details.dispatchEvent(new Event('toggle'));await nextTick()}
afterEach(()=>{app?.unmount();root?.remove();vi.resetAllMocks()})

describe('Grouped audit card',()=>{
  it('loads details only on expansion, keeps filters and paginates without repeating records',async()=>{
    api.auditGroup.mockResolvedValueOnce({total:2,events:[first]}).mockResolvedValueOnce({total:2,events:[first,{...first,id:'event2',action:'update'}]})
    mount();expect(api.auditGroup).not.toHaveBeenCalled()
    expect(root.textContent).toContain('Venda #ABCD123456')
    expect(root.textContent).toContain('Diminuiu 2 un. em Loja · Camiseta azul · INV-ABC12')
    await expand();await vi.waitFor(()=>expect(root.querySelectorAll('.event-list>li')).toHaveLength(1))
    expect(api.auditGroup).toHaveBeenNthCalledWith(1,{...filters,key:group.key,offset:0})
    expect(root.querySelector('a')?.getAttribute('data-target')).toContain('vendas-pdv')
    expect(root.querySelector('.event-list')?.textContent).toContain('5 → 3')
    expect(root.querySelector('.event-list')?.textContent).not.toContain('_context')
    root.querySelector<HTMLButtonElement>('.operation-content>button')!.click()
    await vi.waitFor(()=>expect(root.querySelectorAll('.event-list>li')).toHaveLength(2))
    expect(api.auditGroup).toHaveBeenNthCalledWith(2,{...filters,key:group.key,offset:1})
    expect(root.querySelector('.operation-content>button')).toBeNull()
  })
  it('preserves the operation and offers retry when its detail request fails',async()=>{
    api.auditGroup.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({total:2,events:[first,{...first,id:'event2'}]})
    mount();await expand();await vi.waitFor(()=>expect(root.querySelector('[role="alert"]')).not.toBeNull())
    expect(root.textContent).toContain('Venda #ABCD123456')
    root.querySelector<HTMLButtonElement>('.operation-content>button')!.click()
    await vi.waitFor(()=>expect(root.querySelectorAll('.event-list>li')).toHaveLength(2))
    expect(root.querySelector('[role="alert"]')).toBeNull()
  })
})
