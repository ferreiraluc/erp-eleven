import './assets/main.css'
import './assets/buttons.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import i18n from './i18n'
import { uiText } from './i18n/uiText'
import { useAuthStore } from './stores/auth'
import { resumeVerifiedSession } from './services/sessionResume'

const app = createApp(App)
app.config.globalProperties.$tr = uiText

app.use(createPinia())
const auth = useAuthStore()
window.addEventListener('erp:session-expired', () => { router.replace('/login') })
window.addEventListener('erp:password-required', () => { router.replace('/conta') })
window.addEventListener('storage', (event) => {
  if (event.key === 'auth_token') window.location.reload()
})
function resumeSession() { void resumeVerifiedSession(auth, router) }
window.addEventListener('focus', resumeSession)
document.addEventListener('visibilitychange', resumeSession)
window.addEventListener('pageshow', resumeSession)
app.use(router)
app.use(i18n)

// Wait for router to be ready before mounting
router.isReady().then(() => {
  app.mount('#app')
}).catch((error) => {
  console.error('[ROUTER_ERROR] Router initialization failed:', error)
  // Mount anyway to show error state
  app.mount('#app')
})
