import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import { authAPI, type LoginRequest, type User } from '@/services/api'
import { clearSession, saveToken, storedToken, tokenIsCurrent } from '@/services/sessionStorage'
import i18n from '@/i18n'
import { AuthOperationSuperseded, isAuthOperationSuperseded } from '@/services/authOperation'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)
  const status = ref<'unknown' | 'checking' | 'authenticated' | 'guest' | 'error'>('unknown')
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  let checkedAt = 0
  let checking: Promise<boolean> | null = null
  let checkingToken: string | null = null
  let generation = 0
  let operationEpoch = 0
  const isAuthenticated = computed(() => status.value === 'authenticated' && !!user.value)
  const isOwner = computed(() => user.value?.role === 'ADMIN' && user.value?.email.toLowerCase() === 'lucas@eleven.com')
  const ownSales = computed(() => user.value?.sales_scope === 'own')
  const userRole = computed(() => user.value?.role || '')
  const userName = computed(() => user.value?.nome || '')

  function expire() {
    operationEpoch++
    generation++
    checking = null
    checkingToken = null
    clearSession()
    user.value = null
    token.value = null
    checkedAt = 0
    status.value = 'guest'
    isLoading.value = false
    error.value = null
  }

  async function ensureSession(force = false): Promise<boolean> {
    const saved = storedToken()
    if (!saved || !tokenIsCurrent(saved)) { expire(); return false }
    if (checking && checkingToken === saved) return checking
    if (!force && isAuthenticated.value && saved === token.value && Date.now() - checkedAt < 60000) return true
    const current = ++generation
    // Keep an already verified view mounted during background validation so an
    // ordinary window focus does not discard an in-progress form.
    if (!isAuthenticated.value || token.value !== saved) status.value = 'checking'
    token.value = saved
    checkingToken = saved
    checking = (async () => {
      try {
        const verified = await authAPI.getCurrentUser(saved)
        if (current !== generation || saved !== storedToken()) return false
        user.value = verified
        status.value = 'authenticated'
        checkedAt = Date.now()
        error.value = null
        return true
      } catch (e) {
        if (current !== generation || saved !== storedToken()) return false
        if (axios.isAxiosError(e) && e.response?.status === 401) expire()
        else {
          status.value = 'error'
          user.value = null
          error.value = i18n.global.t('access.connectionError')
        }
        return false
      } finally { if (current === generation) { checking = null; checkingToken = null } }
    })()
    return checking
  }

  function assertOperation(epoch: number, expectedToken: string | null) {
    if (epoch !== operationEpoch || storedToken() !== expectedToken) throw new AuthOperationSuperseded()
  }

  async function login(credentials: LoginRequest, remember = true) {
    expire()
    const operation = operationEpoch
    let expectedToken: string | null = null
    isLoading.value = true
    error.value = null
    try {
      const result = await authAPI.login({ ...credentials, email: credentials.email.trim().toLowerCase() })
      assertOperation(operation, null)
      saveToken(result.access_token, remember)
      expectedToken = result.access_token
      if (!await ensureSession(true)) throw new Error('session_not_verified')
      assertOperation(operation, result.access_token)
      return result
    } catch (e) {
      if (operation !== operationEpoch || storedToken() !== expectedToken || isAuthOperationSuperseded(e)) throw new AuthOperationSuperseded()
      if (!error.value) {
        const status = axios.isAxiosError(e) ? e.response?.status : undefined
        error.value = i18n.global.t(status === 429 ? 'access.tooManyAttempts' : status === 401 || status === 422 ? 'access.invalidLogin' : 'access.connectionError')
      }
      throw e
    } finally { if (operation === operationEpoch) isLoading.value = false }
  }

  async function changePassword(currentPassword: string, newPassword: string) {
    const originalToken = storedToken()
    if (!originalToken || !tokenIsCurrent(originalToken)) { expire(); throw new AuthOperationSuperseded() }
    const operation = ++operationEpoch
    let expectedToken = originalToken
    const remember = localStorage.getItem('auth_token') === originalToken
    try {
      const result = await authAPI.changePassword(currentPassword, newPassword, originalToken)
      assertOperation(operation, originalToken)
      saveToken(result.access_token, remember)
      expectedToken = result.access_token
      generation++
      checking = null
      checkingToken = null
      if (!await ensureSession(true)) throw new Error('session_not_verified')
      assertOperation(operation, result.access_token)
      return result
    } catch (e) {
      if (operation !== operationEpoch || storedToken() !== expectedToken || isAuthOperationSuperseded(e)) throw new AuthOperationSuperseded()
      throw e
    }
  }

  async function logout() {
    const originalToken = storedToken()
    // Remove private UI immediately. Only this captured token may be revoked;
    // a delayed response never clears the next user's identity.
    expire()
    if (originalToken) await authAPI.logout(originalToken)
  }

  window.addEventListener('erp:session-expired', expire)
  return { user, token, status, isLoading, error, isAuthenticated, isOwner, ownSales, userRole, userName,
           login, logout, expire, ensureSession, changePassword, clearError: () => { error.value = null } }
})
