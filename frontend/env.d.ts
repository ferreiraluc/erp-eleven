/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
}

interface Window {
  showNotification?: (message: string, type?: 'success' | 'error' | 'warning' | 'info', description?: string) => void
}
