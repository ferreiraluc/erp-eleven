import { openDropdown } from '@/test/dropdown'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import AuditView from './AuditView.vue'
import pt from '@/locales/pt.json'
const api=vi.hoisted(()=>({audit:vi.fn(),users:vi.fn()}))
const route=vi.hoisted(()=>({query:{quality_run:'01d34342-6471-4c83-bdfa-f339465cab0a'}}))
vi.mock('@/services/access',()=>({accessAPI:api}))
vi.mock('vue-router',()=>({useRoute:()=>route}))
vi.mock('@/components/ModuleHeader.vue',()=>({default:{template:'<header><slot /></header>'}}))
vi.mock('@/components/notifications/QualityPanel.vue',()=>({default:{props:['runId'],template:'<section :data-quality-run="runId" />'}}))
let app:App,root:HTMLDivElement
afterEach(()=>{app?.unmount();root?.remove();vi.resetAllMocks()})
describe('Focused audit view',()=>{
  it('shows logins and mutation summaries without query filters or navigation time',async()=>{
    api.users.mockResolvedValue([{id:'owner',nome:'Lucas'}])
    api.audit.mockResolvedValue({total:3,offset:0,limit:50,active_seconds:0,modules:[],users:[{id:'owner',name:'Lucas',last_seen_at:null,actions:{login:1,create:1,item_permanently_deleted:1}}],events:[]})
    root=document.createElement('div');document.body.append(root)
    app=createApp(AuditView).use(createI18n({legacy:false,locale:'pt',messages:{pt}}));app.mount(root)
    await vi.waitFor(()=>expect(api.users).toHaveBeenCalled())
    expect(root.querySelector('[data-quality-run]')?.getAttribute('data-quality-run')).toBe(route.query.quality_run)
    expect(root.textContent).toContain('Consultas e tempo de navegação não são registrados.')
    expect(root.textContent).not.toContain('Tempo ativo')
    const options=(await openDropdown(Array.from(root.querySelectorAll('.filters .erp-dropdown')).at(-1))).map(node=>node.value)
    expect(options).toContain('login');expect(options).not.toContain('read');expect(options).not.toContain('request')
    expect(root.querySelector('.metrics')?.textContent).toContain('Usuários com eventos')
    expect(root.querySelector('tbody tr')?.textContent).toContain('Lucas12')
  })
})
