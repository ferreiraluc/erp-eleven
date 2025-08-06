import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authAPI, type LoginRequest, type LoginResponse, type User } from '@/services/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Computed
  const isAuthenticated = computed(() => !!token.value && !!user.value)
  const userRole = computed(() => user.value?.role || '')
  const userName = computed(() => user.value?.nome || '')

  // Actions
  const login = async (credentials: LoginRequest) => {
    try {
      isLoading.value = true
      error.value = null

      // First get the token
      const loginResponse = await authAPI.login(credentials)
      token.value = loginResponse.access_token
      
      // Store token in localStorage
      localStorage.setItem('auth_token', loginResponse.access_token)
      
      // Then get user information
      const userResponse = await authAPI.getCurrentUser()
      user.value = userResponse
      
      // Store user data in localStorage
      localStorage.setItem('user_data', JSON.stringify(userResponse))
      
      return loginResponse
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Login failed'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  const logout = async () => {
    try {
      await authAPI.logout()
    } catch (err) {
      console.error('Logout error:', err)
    } finally {
      // Clear state regardless of API call success
      token.value = null
      user.value = null
      error.value = null
      
      // Clear localStorage
      localStorage.removeItem('auth_token')
      localStorage.removeItem('user_data')
    }
  }

  const loadStoredAuth = () => {
    const storedToken = localStorage.getItem('auth_token')
    const storedUser = localStorage.getItem('user_data')
    
    if (storedToken && storedUser) {
      token.value = storedToken
      try {
        user.value = JSON.parse(storedUser)
      } catch (err) {
        console.error('Error parsing stored user data:', err)
        logout()
      }
    }
  }

  const clearError = () => {
    error.value = null
  }

  // Note: loadStoredAuth() will be called from App.vue onMounted

  return {
    // State
    user,
    token,
    isLoading,
    error,
    
    // Computed
    isAuthenticated,
    userRole,
    userName,
    
    // Actions
    login,
    logout,
    loadStoredAuth,
    clearError,
  }
})