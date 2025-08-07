import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [
    vue(),
    mode === 'development' ? vueDevTools() : undefined,
  ].filter(Boolean),
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: mode === 'development',
    minify: 'esbuild',
    target: 'esnext',
    cssCodeSplit: true,
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia'],
          ui: ['@headlessui/vue', '@heroicons/vue'],
          charts: ['chart.js', 'vue-chartjs'],
          utils: ['axios', '@vueuse/core'],
        },
        entryFileNames: 'assets/[name]-[hash].js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash].[ext]',
      },
    },
    reportCompressedSize: false,
    emptyOutDir: true,
  },
  base: process.env.NODE_ENV === 'production' ? '/' : '/',
  define: {
    __VUE_OPTIONS_API__: false,
    __VUE_PROD_DEVTOOLS__: false,
  },
  esbuild: {
    drop: mode === 'production' ? ['console', 'debugger'] : [],
  },
  server: {
    port: 3000,
    host: true,
    proxy: mode === 'development' ? {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
    } : undefined,
  },
  preview: {
    port: 4173,
    host: true,
  },
}))
