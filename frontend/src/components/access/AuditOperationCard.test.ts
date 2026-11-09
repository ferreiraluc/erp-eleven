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
function mount(groupOverride:AuditGroup=group){root=document.createElement('div');document.body.append(root);app=createApp(AuditOperationCard,{group:groupOverride,filters}).use(createI18n({legacy:false,locale:'pt',messages:{pt}}));app.component('router-link',{props:['to'],template:'<a :data-target="JSON.stringify(to)"><slot /></a>'});app.mount(root)}
async function expand(){const details=root.querySelector('details')!;details.open=true;details.dispatchEvent(new Event('toggle'));await nextTick()}
afterEach(()=>{app?.unmount();root?.remove();vi.resetAllMocks()})

describe('Grouped audit card',()=>{
  it('loads details only on expansion, keeps filters and paginates without repeating records',async()=>{
    api.auditGroup.mockResolvedValueOnce({total:2,events:[first]}).mockResolvedValueOnce({total:2,events:[first,{...first,id:'event2',action:'update'}]})
    mount();expect(api.auditGroup).not.toHaveBeenCalled()
    expect(root.textContent).toContain('Venda #ABCD123456')
    expect(root.textContent).toContain('Saída de estoque · 2 un. · Loja · Camiseta azul · INV-ABC12')
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

it('keeps a single customer change concise and technical identifiers behind a separate disclosure',async()=>{
  const customer={...first,entity:'clientes',entity_id:'customer-id',module:'clientes',action:'update',actor_name:'Lucas',occurred_at:'2026-11-09T01:08:25Z',changes:{nome:{changed:true},updated_at:{changed:true}}}
  const single:AuditGroup={...group,key:'request:customer',kind:'operation',event_count:1,sale_id:null,sale_code:null,actor_name:'Lucas',first_at:customer.occurred_at,last_at:customer.occurred_at,samples:[customer],summary_event:customer}
  api.auditGroup.mockResolvedValue({total:1,events:[customer]})
  mount(single)
  expect(root.querySelector('.operation-heading strong')?.textContent).toBe('Alteração de nome do cliente')
  expect(root.querySelector('.record-count')).toBeNull()
  expect(root.querySelector('.operation-preview')).toBeNull()
  expect(root.querySelector('.operation-heading small')?.textContent).toContain('08/11/2026, 22:08:25')
  await expand();await vi.waitFor(()=>expect(root.querySelector('.event-details')).not.toBeNull())
  expect(root.querySelectorAll('.event-list>li>strong')).toHaveLength(0)
  expect(root.querySelector('.event-details>ul')?.textContent).toBe('Nome: Campo alterado')
  expect(root.querySelector('.event-details>ul')?.textContent).not.toContain('updated_at')
  expect(root.querySelector('.technical-details')?.hasAttribute('open')).toBe(false)
  expect(root.querySelector('.technical-details')?.textContent).toContain('customer-id')
  expect(root.querySelector('.technical-details')?.textContent).toContain('request1')
})
