import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { Script } from 'node:vm'

const root = resolve(process.argv[2] || 'dist')
const html = readFileSync(resolve(root, 'index.html'), 'utf8')
const bootstrap = html.match(/<script src="\/loading-fallback\.js\?v=([a-f0-9]{12})" data-release="([a-f0-9]{7,12}|local)"><\/script>/)
assert(bootstrap, 'Missing versioned recovery bootstrap')
const [markup, version, release] = bootstrap
assert.equal(createHash('sha256').update(readFileSync(resolve(root, 'loading-fallback.js'))).digest('hex').slice(0, 12), version)
const assets = [...html.matchAll(/(?:href|src)="(\/assets\/[^"?]+)"/g)]
assert(assets.length >= 2, 'No entry assets in HTML')
for (const asset of assets) {
  assert(asset[1].startsWith(`/assets/${release}/`), `Unversioned asset: ${asset[1]}`)
  assert(html.indexOf(markup) < asset.index, 'Recovery must load before build assets')
  assert(existsSync(resolve(root, asset[1].slice(1))), `Missing asset: ${asset[1]}`)
}
assert(!existsSync(resolve(root, '_redirects')), 'Do not rewrite missing assets to HTML')
const pushWorker = resolve(root, 'notifications-sw.js')
assert(existsSync(pushWorker), 'Missing notification service worker')
new Script(readFileSync(pushWorker, 'utf8'), { filename: 'notifications-sw.js' })
console.log(`Build ${release}: versioned bootstrap and ${assets.length} entry assets verified`)
