import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { AxiosError } from 'axios'
import { useAuthStore } from './auth'
import { authAPI, type User } from '@/services/api'
import { saveToken, storedToken, tokenIsCurrent } from '@/services/sessionStorage'

function token(id='one',exp=Date.now()/1000+3600){return 'x.'+btoa(JSON.stringify({sid:id,exp}))+'.x'}
function user(name='Junior'):User{return {id:name,nome:name,email:name.toLowerCase()+'@eleven.com',role:name==='Lucas'?'ADMIN':'GERENTE',ativo:true,must_change_password:false,sales_scope:name==='Lucas'?'all':'own',sales_seller:name,vendedor_id:name,created_at:'',updated_at:''}}
function failure(status:number){const e=new AxiosError('failed');e.response={status,data:{},statusText:'',headers:{},config:{headers:{} as never}};return e}
beforeEach(()=>{localStorage.clear();sessionStorage.clear();setActivePinia(createPinia())})

describe('verified sessions',()=>{
  it('does not trust cached user data or an old token without session id',async()=>{
    localStorage.setItem('user_data',JSON.stringify(user('Lucas')))
    localStorage.setItem('auth_token','x.'+btoa(JSON.stringify({exp:Date.now()/1000+3600}))+'.x')
    const get=vi.spyOn(authAPI,'getCurrentUser');const auth=useAuthStore()
    expect(await auth.ensureSession()).toBe(false);expect(auth.isOwner).toBe(false);expect(auth.user).toBe(null);expect(get).not.toHaveBeenCalled();expect(storedToken()).toBe(null)
  })
  it('fetches current permissions before entering the application',async()=>{
    saveToken(token());localStorage.setItem('user_data',JSON.stringify(user('Lucas')))
    const get=vi.spyOn(authAPI,'getCurrentUser').mockResolvedValue(user())
    const auth=useAuthStore();expect(auth.isAuthenticated).toBe(false)
    expect(await auth.ensureSession()).toBe(true);expect(auth.ownSales).toBe(true);expect(auth.isOwner).toBe(false)
    await auth.ensureSession();expect(get).toHaveBeenCalledTimes(1)
  })
  it('clears expired/revoked sessions and never shows components as authenticated',async()=>{
    saveToken(token());vi.spyOn(authAPI,'getCurrentUser').mockRejectedValue(failure(401))
    const auth=useAuthStore();expect(await auth.ensureSession()).toBe(false);expect(auth.status).toBe('guest');expect(storedToken()).toBe(null)
  })
  it('keeps a retryable session through a network outage but blocks private screens',async()=>{
    saveToken(token());const get=vi.spyOn(authAPI,'getCurrentUser').mockRejectedValue(failure(503));const auth=useAuthStore()
    expect(await auth.ensureSession()).toBe(false);expect(auth.status).toBe('error');expect(auth.isAuthenticated).toBe(false);expect(storedToken()).not.toBe(null)
    get.mockResolvedValue(user());expect(await auth.ensureSession()).toBe(true)
  })
  it('does not resurrect a session when its old request completes after logout',async()=>{
    saveToken(token());let complete!:(value:User)=>void
    vi.spyOn(authAPI,'getCurrentUser').mockReturnValue(new Promise(r=>{complete=r}))
    const auth=useAuthStore(),pending=auth.ensureSession();auth.expire();complete(user('Lucas'))
    expect(await pending).toBe(false);expect(auth.isAuthenticated).toBe(false);expect(auth.user).toBe(null)
  })
  it('revalidates permissions on resume and rejects token expiry even within the cache window',async()=>{
    saveToken(token());const get=vi.spyOn(authAPI,'getCurrentUser').mockResolvedValue(user('Lucas'));const auth=useAuthStore();await auth.ensureSession()
    get.mockResolvedValue(user());await auth.ensureSession(true);expect(auth.ownSales).toBe(true)
    saveToken(token('expired',Date.now()/1000-1));expect(await auth.ensureSession()).toBe(false)
  })
  it('remember-me false uses session storage and canonical email',async()=>{
    const request=vi.spyOn(authAPI,'login').mockResolvedValue({access_token:token(),token_type:'bearer',expires_in:3600});vi.spyOn(authAPI,'getCurrentUser').mockResolvedValue(user())
    await useAuthStore().login({email:' JUNIOR@eleven.com ',senha:'example-password'},false)
    expect(request).toHaveBeenCalledWith({email:'junior@eleven.com',senha:'example-password'});expect(localStorage.getItem('auth_token')).toBe(null);expect(sessionStorage.getItem('auth_token')).not.toBe(null)
  })
  it('updates token after changing password and clears account state even if logout network fails',async()=>{
    const newToken=token('new')
    saveToken(token());vi.spyOn(authAPI,'getCurrentUser').mockResolvedValue(user());vi.spyOn(authAPI,'changePassword').mockResolvedValue({access_token:newToken,token_type:'bearer',expires_in:3600})
    const auth=useAuthStore();await auth.ensureSession();await auth.changePassword('old','newpass');expect(storedToken()).toBe(newToken)
    vi.spyOn(authAPI,'logout').mockRejectedValue(new Error('offline'));await expect(auth.logout()).rejects.toThrow();expect(auth.isAuthenticated).toBe(false);expect(storedToken()).toBe(null)
  })
  it('validates malformed and expired token payloads',()=>{
    for(const value of ['', 'a.b.c',token('old',1)])expect(tokenIsCurrent(value)).toBe(false)
    expect(tokenIsCurrent(token())).toBe(true)
  })
  it('keeps forms mounted on focus and ignores a background check superseded by a password change',async()=>{
    saveToken(token());const get=vi.spyOn(authAPI,'getCurrentUser').mockResolvedValue(user());const auth=useAuthStore();await auth.ensureSession()
    let complete!:(value:User)=>void
    get.mockReturnValueOnce(new Promise(r=>{complete=r}))
    const background=auth.ensureSession(true)
    expect(auth.status).toBe('authenticated')
    vi.spyOn(authAPI,'changePassword').mockResolvedValue({access_token:token('changed'),token_type:'bearer',expires_in:3600})
    await auth.changePassword('old-password','new-password')
    complete(user('Lucas'));expect(await background).toBe(false)
    expect(auth.user?.nome).toBe('Junior');expect(auth.token).toBe(storedToken());expect(auth.isAuthenticated).toBe(true)
  })
})
