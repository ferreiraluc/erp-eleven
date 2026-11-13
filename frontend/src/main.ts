import './assets/main.css'
import './assets/buttons.css'
import './assets/dialogs.css'
import './assets/ios.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import i18n from './i18n'
import { uiText } from './i18n/uiText'
import { useAuthStore } from './stores/auth'
import { resumeVerifiedSession } from './services/sessionResume'
import { initializeNativeSession, resetNativeSession } from './services/sessionStorage'
import {
  isNativeSession,
  isNativeSessionStorageError,
  nativeSessionStorageMessage,
} from './services/nativeSessionVault'
import { initializeNativeLifecycle } from './services/nativeRuntime'

window.dispatchEvent(new Event('erp:entry-ready'))
async function bootstrap() {
  await initializeNativeSession()
  const app = createApp(App)
  app.config.globalProperties.$tr = uiText

  app.use(createPinia())
  const auth = useAuthStore()
  window.addEventListener('erp:session-expired', () => {
    router.replace('/login')
  })
  window.addEventListener('erp:password-required', () => {
    router.replace('/conta')
  })
  window.addEventListener('storage', (event) => {
    if (event.key === 'auth_token') window.location.reload()
  })
  window.addEventListener('erp:native-notification-open', () => {
    void router.push('/notificacoes')
  })
  function resumeSession() {
    void resumeVerifiedSession(auth, router)
  }
  window.addEventListener('focus', resumeSession)
  document.addEventListener('visibilitychange', resumeSession)
  window.addEventListener('pageshow', resumeSession)
  router.onError((error) => {
    window.dispatchEvent(new CustomEvent('erp:route-load-error', { detail: error }))
  })
  app.use(i18n)
  app.use(router)
  await initializeNativeLifecycle(auth, router)
  if (isNativeSession()) {
    document.documentElement.classList.add('eleven-native')
    const { initializeNativeFileCleanup } = await import('./services/nativeFiles')
    await initializeNativeFileCleanup()
  }

  // Wait for router to be ready before mounting
  await router.isReady()
  app.mount('#app')
  window.dispatchEvent(new Event('erp:application-ready'))
}
bootstrap().catch((error) => {
  console.error('[ROUTER_ERROR] Router initialization failed:', error)
  if (isNativeSession()) {
    // Keep recovery usable even when the secure vault cannot be opened. No token,
    // OS error details or credentials are rendered in the error panel.
    const panel = document.createElement('section')
    panel.id = 'erp-load-recovery'
    panel.className = 'native-boot-recovery'
    panel.setAttribute('role', 'alert')
    const text = document.createElement('p')
    text.textContent = isNativeSessionStorageError(error)
      ? nativeSessionStorageMessage(String(i18n.global.locale.value))
      : 'Não foi possível iniciar o aplicativo. Toque em Atualizar para tentar novamente.'
    const retry = document.createElement('button')
    retry.className = 'erp-button erp-button--primary'
    retry.textContent = String(i18n.global.t('common.refresh'))
    retry.onclick = () => window.location.reload()
    const reset = document.createElement('button')
    reset.className = 'erp-button erp-button--secondary'
    reset.textContent = 'Esquecer login neste aparelho'
    reset.onclick = async () => {
      reset.disabled = true
      try {
        await resetNativeSession()
        window.location.reload()
      } catch {
        reset.disabled = false
      }
    }
    panel.append(text, retry)
    if (isNativeSessionStorageError(error)) panel.append(reset)
    document.getElementById('app')?.replaceChildren(panel)
  }
  // Keep the independent recovery screen instead of mounting an empty shell.
  window.dispatchEvent(new CustomEvent('erp:boot-error', { detail: error }))
})
