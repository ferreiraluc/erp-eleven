import { fileURLToPath, URL } from 'node:url'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig(async ({ mode }) => {
  // A missing asset used to receive a permanent redirect to index.html. New
  // release paths also bypass cached redirects for unchanged vendor bundles.
  let revision = process.env.RENDER_GIT_COMMIT || process.env.GITHUB_SHA || ''
  if (!revision) {
    try { revision = execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim() } catch { /* source archive */ }
  }
  const release = /^[a-f0-9]{7,40}$/i.test(revision) ? revision.slice(0, 12) : 'local'
  const assetDirectory = `assets/${release}`
  const recoveryVersion = createHash('sha256').update(readFileSync(new URL('./public/loading-fallback.js', import.meta.url))).digest('hex').slice(0, 12)
  const plugins: any[] = [vue(), {
    name: 'eleven-release-bootstrap',
    transformIndexHtml: {
      order: 'pre',
      handler: (html: string) => html.replace('src="/loading-fallback.js"', `src="/loading-fallback.js?v=${recoveryVersion}" data-release="${release}"`),
    },
  }]

  if (mode === 'development') {
    const { default: vueDevTools } = await import('vite-plugin-vue-devtools')
    plugins.push(vueDevTools())
  }

  return {
  plugins,
  worker: { format: 'es' },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: assetDirectory,
    sourcemap: mode === 'development',
    minify: 'esbuild',
    target: 'esnext',
    cssCodeSplit: true,
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia'],
          charts: ['chart.js', 'vue-chartjs'],
          utils: ['axios'],
        },
        entryFileNames: `${assetDirectory}/[name]-[hash].js`,
        chunkFileNames: `${assetDirectory}/[name]-[hash].js`,
        assetFileNames: `${assetDirectory}/[name]-[hash].[ext]`,
      },
    },
    reportCompressedSize: false,
    emptyOutDir: true,
  },
  base: process.env.NODE_ENV === 'production' ? '/' : '/',
  define: {
    __VUE_OPTIONS_API__: false,
    __VUE_PROD_DEVTOOLS__: false,
    // vue-i18n 9 defaults to generated functions, which violate script-src self.
    __INTLIFY_JIT_COMPILATION__: true,
    __INTLIFY_DROP_MESSAGE_COMPILER__: false,
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
  }
})
