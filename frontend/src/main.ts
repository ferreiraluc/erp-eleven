import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import i18n from './i18n'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(i18n)

// Wait for router to be ready before mounting
router.isReady().then(() => {
  console.log('[ROUTER] Router is ready, mounting app...')
  app.mount('#app')
  console.log('[APP] App mounted successfully')
}).catch((error) => {
  console.error('[ROUTER_ERROR] Router initialization failed:', error)
  // Mount anyway to show error state
  app.mount('#app')
})
