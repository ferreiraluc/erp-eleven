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
  app.mount('#app')
}).catch((error) => {
  console.error('Router initialization failed:', error)
  // Mount anyway to show error state
  app.mount('#app')
})
