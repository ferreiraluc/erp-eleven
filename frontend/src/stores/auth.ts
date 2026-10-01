import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import { authAPI, type LoginRequest, type User } from '@/services/api'
import { clearSession, saveToken, storedToken, tokenIsCurrent } from '@/services/sessionStorage'
import i18n from '@/i18n'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)
  const status = ref<'unknown' | 'checking' | 'authenticated' | 'guest' | 'error'>('unknown')
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  let checkedAt = 0
  let checking: Promise<boolean> | null = null
  let generation = 0
  const isAuthenticated = computed(() => status.value === 'authenticated' && !!user.value)
  const isOwner = computed(() => user.value?.role === 'ADMIN' && user.value?.email.toLowerCase() === 'lucas@eleven.com')
  const ownSales = computed(() => user.value?.sales_scope === 'own')
  const userRole = computed(() => user.value?.role || '')
  const userName = computed(() => user.value?.nome || '')

  function expire() {
    generation++
    checking = null
    clearSession()
    user.value = null
    token.value = null
    checkedAt = 0
    status.value = 'guest'
  }

  async function ensureSession(force = false): Promise<boolean> {
    const saved = storedToken()
    if (!saved || !tokenIsCurrent(saved)) { expire(); return false }
    if (checking) return checking
    if (!force && isAuthenticated.value && saved === token.value && Date.now() - checkedAt < 60000) return true
    const current = ++generation
    // Keep an already verified view mounted during background validation so an
    // ordinary window focus does not discard an in-progress form.
    if (!isAuthenticated.value || token.value !== saved) status.value = 'checking'
    token.value = saved
    checking = (async () => {
      try {
        const verified = await authAPI.getCurrentUser()
        if (current !== generation || saved !== storedToken()) return false
        user.value = verified
        status.value = 'authenticated'
        checkedAt = Date.now()
        error.value = null
        return true
      } catch (e) {
        if (current !== generation) return false
        if (axios.isAxiosError(e) && e.response?.status === 401) expire()
        else {
          status.value = 'error'
          user.value = null
          error.value = i18n.global.t('access.connectionError')
        }
        return false
      } finally { if (current === generation) checking = null }
    })()
    return checking
  }

  async function login(credentials: LoginRequest, remember = true) {
    isLoading.value = true
    error.value = null
    expire()
    try {
      const result = await authAPI.login({ ...credentials, email: credentials.email.trim().toLowerCase() })
      saveToken(result.access_token, remember)
      if (!await ensureSession(true)) throw new Error('session_not_verified')
      return result
    } catch (e) {
      if (!error.value) error.value = i18n.global.t(axios.isAxiosError(e) && e.response?.status === 401 ? 'access.invalidLogin' : 'access.connectionError')
      throw e
    } finally { isLoading.value = false }
  }

  async function changePassword(currentPassword: string, newPassword: string) {
    const remember = !!localStorage.getItem('auth_token')
    const result = await authAPI.changePassword(currentPassword, newPassword)
    saveToken(result.access_token, remember)
    generation++
    checking = null
    if (!await ensureSession(true)) throw new Error('session_not_verified')
  }

  async function logout() {
    try { await authAPI.logout() } finally { expire() }
  }

  window.addEventListener('erp:session-expired', expire)
  return { user, token, status, isLoading, error, isAuthenticated, isOwner, ownSales, userRole, userName,
           login, logout, expire, ensureSession, changePassword, clearError: () => { error.value = null } }
})
