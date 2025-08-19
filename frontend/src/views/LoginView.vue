<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-header">
        <!-- Logo and title -->
        <div class="logo">
          <svg class="logo-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
          </svg>
        </div>
        <h2 class="login-title">{{ $t('auth.welcomeTitle') }}</h2>
        <p class="login-subtitle">{{ $t('auth.signInSubtitle') }}</p>
      </div>
      
      <div class="card">
        <div class="card-body">
          <form @submit.prevent="handleLogin" class="login-form">
            <div v-if="authStore.error" class="error-message">
              <div class="error-content">
                <svg class="error-icon" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                </svg>
                <p class="error-text">{{ authStore.error }}</p>
              </div>
            </div>

            <div class="form-group">
              <label for="email" class="form-label">{{ $t('auth.emailLabel') }}</label>
              <input
                id="email"
                v-model="credentials.email"
                type="email"
                autocomplete="email"
                required
                class="input-field"
                :placeholder="$t('auth.emailPlaceholder')"
                :disabled="authStore.isLoading"
              />
            </div>

            <div class="form-group">
              <label for="password" class="form-label">{{ $t('auth.passwordLabel') }}</label>
              <input
                id="password"
                v-model="credentials.senha"
                type="password"
                autocomplete="current-password"
                required
                class="input-field"
                :placeholder="$t('auth.passwordPlaceholder')"
                :disabled="authStore.isLoading"
              />
            </div>

            <div class="form-options">
              <div class="remember-me">
                <input
                  id="remember-me"
                  name="remember-me"
                  type="checkbox"
                  class="checkbox"
                />
                <label for="remember-me" class="checkbox-label">{{ $t('auth.rememberMe') }}</label>
              </div>

              <div class="forgot-password">
                <a href="#" class="forgot-link">{{ $t('auth.forgotPassword') }}</a>
              </div>
            </div>

            <button
              type="submit"
              class="btn-primary login-button"
              :disabled="authStore.isLoading"
            >
              <svg
                v-if="authStore.isLoading"
                class="loading-spinner"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle class="spinner-track" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="spinner-path" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              {{ authStore.isLoading ? $t('auth.signingIn') : $t('auth.signInButton') }}
            </button>
          </form>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const { t } = useI18n()  // Internationalization hook
const authStore = useAuthStore()

const credentials = ref({
  email: '',
  senha: ''
})

const handleLogin = async () => {
  try {
    await authStore.login(credentials.value)
    router.push('/dashboard')
  } catch (error) {
    // Error handled by store
  }
}

onMounted(() => {
  // Clear any previous errors
  authStore.clearError()

  // DEBUG: Verifica se API base foi carregada corretamente
  console.log('🌐 VITE_API_BASE_URL:', import.meta.env.VITE_API_BASE_URL)

  
  // If already authenticated, redirect to dashboard
  if (authStore.isAuthenticated) {
    router.push('/dashboard')
  }
})
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  padding: 2rem;
}

.login-box {
  width: 100%;
  max-width: 28rem;
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.login-header {
  text-align: center;
}

.logo {
  margin: 0 auto 2rem;
  width: 5rem;
  height: 5rem;
  background-color: #2563eb;
  border-radius: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-icon {
  width: 2.5rem;
  height: 2.5rem;
  color: white;
}

.login-title {
  margin: 1.5rem 0 0.5rem 0;
  font-size: 1.875rem;
  font-weight: 700;
  color: #111827;
}

.login-subtitle {
  margin: 0;
  font-size: 0.875rem;
  color: #6b7280;
}

.card-body {
  padding: 2rem;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.error-message {
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 0.5rem;
  padding: 1rem;
}

.error-content {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
}

.error-icon {
  width: 1.25rem;
  height: 1.25rem;
  color: #dc2626;
  flex-shrink: 0;
}

.error-text {
  margin: 0;
  font-size: 0.875rem;
  color: #991b1b;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
}

.form-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.remember-me {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.checkbox {
  width: 1rem;
  height: 1rem;
  color: #2563eb;
  border: 1px solid #d1d5db;
  border-radius: 0.25rem;
}

.checkbox-label {
  font-size: 0.875rem;
  color: #111827;
  cursor: pointer;
}

.forgot-password {
  font-size: 0.875rem;
}

.forgot-link {
  color: #2563eb;
  text-decoration: none;
  font-weight: 500;
}

.forgot-link:hover {
  color: #1d4ed8;
}

.login-button {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  font-size: 1rem;
}

.loading-spinner {
  width: 1.25rem;
  height: 1.25rem;
  color: white;
  animation: spin 1s linear infinite;
}

.spinner-track {
  opacity: 0.25;
}

.spinner-path {
  opacity: 0.75;
}

.test-credentials {
  text-align: center;
}

.test-credentials p {
  margin: 0;
  font-size: 0.75rem;
  color: #6b7280;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>