import { createApp } from 'vue'

// Simple test app
const app = createApp({
  template: `
    <div style="padding: 20px; font-family: Arial, sans-serif;">
      <h1>ERP Eleven Frontend - Debug Mode</h1>
      <p>✅ Vue.js is working correctly</p>
      <p>Environment: {{ env }}</p>
      <p>API URL: {{ apiUrl }}</p>
    </div>
  `,
  data() {
    return {
      env: import.meta.env.MODE,
      apiUrl: import.meta.env.VITE_API_BASE_URL || 'Not configured'
    }
  }
})

app.mount('#app')