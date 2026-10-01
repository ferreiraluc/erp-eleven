import { beforeEach, expect, it } from 'vitest'
import { AxiosError, type AxiosAdapter } from 'axios'
import api from './api'
import { saveToken, storedToken } from './sessionStorage'
beforeEach(()=>{localStorage.clear();sessionStorage.clear()})
it('a delayed 401 from a previous account does not sign out the current account',async()=>{
  saveToken('old')
  const adapter:AxiosAdapter=async config=>{
    expect(config.headers.Authorization).toBe('Bearer old');saveToken('current')
    throw new AxiosError('expired','ERR_BAD_REQUEST',config,undefined,{status:401,statusText:'',headers:{},data:{},config})
  }
  await expect(api.get('/api/example',{adapter})).rejects.toThrow();expect(storedToken()).toBe('current')
})
it('a 401 for the current token clears stored identity',async()=>{
  saveToken('current');localStorage.setItem('user_data','old identity')
  const adapter:AxiosAdapter=async config=>{throw new AxiosError('expired','ERR_BAD_REQUEST',config,undefined,{status:401,statusText:'',headers:{},data:{},config})}
  await expect(api.get('/api/example',{adapter})).rejects.toThrow();expect(storedToken()).toBe(null);expect(localStorage.getItem('user_data')).toBe(null)
})
