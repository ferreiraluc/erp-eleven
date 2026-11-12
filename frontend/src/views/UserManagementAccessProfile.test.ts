import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import i18n from '@/i18n'
import { chooseDropdown } from '@/test/dropdown'
import UserManagementView from './UserManagementView.vue'
import type { User } from '@/services/api'

const mocks = vi.hoisted(() => ({ users:vi.fn(), create:vi.fn(), update:vi.fn(), vendors:vi.fn(), overview:vi.fn() }))
vi.mock('@/services/access', () => ({ accessAPI:mocks }))
vi.mock('@/services/api', () => ({ vendorsAPI:{getAll:mocks.vendors} }))
vi.mock('@/services/salesBi', () => ({ salesBi:{overview:mocks.overview} }))
vi.mock('@/stores/auth', () => ({ useAuthStore:()=>({user:{id:'owner'}}) }))
const account = (id:string, access_profile:'standard'|'reseller' = 'standard'):User => ({ id,nome:id,email:`${id}@example.test`,ativo:true,must_change_password:false,role:id==='owner'?'ADMIN':'VENDEDOR',sales_scope:id==='owner'?'all':'own',sales_seller:null,vendedor_id:null,access_profile,created_at:'',updated_at:'' })
let app:App|undefined, container:HTMLElement
const settle=async()=>{for(let i=0;i<8;i++){await nextTick();await Promise.resolve()}}
async function mount(){
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/usuarios',component:UserManagementView}]})
  await router.push('/usuarios');await router.isReady()
  app=createApp(UserManagementView).use(router).use(i18n);app.mount(container);await settle()
}
function button(label:string){return Array.from(container.querySelectorAll<HTMLButtonElement>('button')).find(b=>b.textContent?.trim()===label)!}
function inputValue(input:HTMLInputElement,value:string){input.value=value;input.dispatchEvent(new Event('input',{bubbles:true}))}
beforeEach(()=>{
  vi.resetAllMocks();i18n.global.locale.value='pt'
  container=document.createElement('div');document.body.append(container)
  mocks.users.mockResolvedValue([]);mocks.vendors.mockResolvedValue([]);mocks.overview.mockResolvedValue({sellers:[]})
  mocks.create.mockResolvedValue(account('new','reseller'));mocks.update.mockResolvedValue(account('reseller','reseller'))
})
afterEach(()=>{app?.unmount();app=undefined;container.remove()})

describe('User access profile form',()=>{
  it('creates a read-only reseller without requiring financial vendor bindings',async()=>{
    await mount();button('Adicionar usuário').click();await settle()
    expect(container.querySelector('button[aria-label="Vendedor no ERP"]')).not.toBeNull()
    await chooseDropdown(container.querySelector('button[aria-label="Perfil"]'),'reseller');await settle()
    expect(container.querySelector('button[aria-label="Vendedor no ERP"]')).toBeNull()
    expect(container.querySelector('button[aria-label="Acesso às vendas"]')).toBeNull()
    expect(container.querySelector('input[aria-label="Nome nas planilhas"]')).toBeNull()
    expect(container.querySelector('.profile-help')?.textContent).toContain('Perfil de consulta')
    const form=container.querySelector<HTMLFormElement>('form')!
    inputValue(form.querySelector('input[minlength="2"]')!,'Parceiro teste')
    inputValue(form.querySelector('input[type="email"]')!,'partner@example.test')
    inputValue(form.querySelector('input[type="password"]')!,'fixture-password')
    await settle();expect(form.checkValidity()).toBe(true)
    form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await settle()
    expect(mocks.create).toHaveBeenCalledWith(expect.objectContaining({access_profile:'reseller',sales_scope:'own',vendedor_id:null,sales_seller:null,nome:'Parceiro teste'}))
    expect(mocks.update).not.toHaveBeenCalled()
  })

  it('loads an existing reseller profile and restores team binding requirements when changed',async()=>{
    mocks.users.mockResolvedValue([account('reseller','reseller')])
    await mount();expect(container.querySelector('tbody')?.textContent).toContain('Sem acesso às vendas')
    button('Editar').click();await settle()
    const profile=container.querySelector<HTMLButtonElement>('button[aria-label="Perfil"]')!
    expect(profile.textContent).toContain('Revendedor — somente consulta')
    await chooseDropdown(profile,'standard');await settle()
    expect(container.querySelector('button[aria-label="Vendedor no ERP"]')).not.toBeNull()
    expect(container.querySelector('input[aria-label="Nome nas planilhas"]')?.hasAttribute('required')).toBe(true)
    expect(container.querySelector<HTMLFormElement>('form')!.checkValidity()).toBe(false)
    await chooseDropdown(profile,'reseller');await settle()
    container.querySelector('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await settle()
    expect(mocks.update).toHaveBeenCalledWith('reseller',expect.objectContaining({access_profile:'reseller',sales_scope:'own'}))
  })

  it('keeps the current administrator profile protected',async()=>{
    mocks.users.mockResolvedValue([account('owner')]);await mount();button('Editar').click();await settle()
    expect(container.querySelector<HTMLButtonElement>('button[aria-label="Perfil"]')?.disabled).toBe(true)
  })
})
