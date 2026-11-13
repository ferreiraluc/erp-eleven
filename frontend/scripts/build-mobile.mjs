import { spawnSync } from 'node:child_process'
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('..', import.meta.url))
const api = new URL(process.env.MOBILE_API_BASE_URL || 'https://erp-eleven-backend.onrender.com')
if (api.protocol !== 'https:' || api.username || api.password || api.search || api.hash || api.pathname !== '/') {
  throw new Error('MOBILE_API_BASE_URL deve ser uma origem HTTPS, sem credenciais, caminho, query ou fragmento.')
}
const result = spawnSync(process.execPath, ['node_modules/vite/bin/vite.js', 'build', '--mode', 'mobile', '--outDir', 'dist-mobile'], {
  cwd: root, stdio: 'inherit',
  env: { ...process.env, VITE_API_BASE_URL: api.origin, VITE_MOBILE_BUILD: 'true' },
})
if (result.status !== 0) process.exit(result.status || 1)
const path = new URL('../dist-mobile/index.html', import.meta.url)
let html = readFileSync(path, 'utf8')
const policy = [
  "default-src 'self'", "base-uri 'self'", "object-src 'none'", "form-action 'none'",
  "script-src 'self' 'wasm-unsafe-eval'", "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:", "font-src 'self' data:",
  `connect-src 'self' ${api.origin}`, "worker-src 'self' blob:", "frame-src 'self' blob:",
].join('; ')
html = html.replace('<meta charset="UTF-8">', `<meta charset="UTF-8">\n    <meta http-equiv="Content-Security-Policy" content="${policy}">`)
html = html.replace('width=device-width, initial-scale=1.0', 'width=device-width, initial-scale=1.0, viewport-fit=cover')
writeFileSync(path, html)
writeFileSync(new URL('../dist-mobile/mobile-build.json', import.meta.url), JSON.stringify({
  platform: 'capacitor', apiOrigin: api.origin, version: '1.0.0',
  release: html.match(/data-release="([^"]+)"/)?.[1],
}, null, 2) + '\n')
console.log(`Mobile bundle: API ${api.origin}; interface incorporada ao aplicativo.`)
