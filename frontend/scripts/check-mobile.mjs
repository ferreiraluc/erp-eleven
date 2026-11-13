import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('..', import.meta.url))
const read = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
const result = spawnSync(process.execPath, ['scripts/check-build.mjs', 'dist-mobile'], { cwd: root, stdio: 'inherit' })
assert.equal(result.status, 0, 'Mobile bundle is incomplete')
const build = JSON.parse(read('dist-mobile/mobile-build.json'))
assert.equal(new URL(build.apiOrigin).protocol, 'https:')
const html = read('dist-mobile/index.html')
assert(html.includes('viewport-fit=cover'))
assert(html.includes('Content-Security-Policy'))
assert(html.includes(`connect-src 'self' ${build.apiOrigin}`))
assert(!html.includes("script-src 'self' 'unsafe-eval'"))
for (const path of ['android/app/src/main/assets/capacitor.config.json', 'ios/App/App/capacitor.config.json']) {
  assert(existsSync(new URL(`../${path}`, import.meta.url)), 'Run cap sync before mobile:check')
  const config = JSON.parse(read(path))
  assert.equal(config.appId, 'com.elevenparispy.erp')
  assert(!config.server.url, 'Production app must bundle its frontend, never load a remote server.url')
  assert.equal(config.server.cleartext, false)
  assert(!config.server.allowNavigation?.length, 'External pages must not get the native bridge')
  assert.equal(config.android.webContentsDebuggingEnabled, false)
  assert.equal(config.ios.webContentsDebuggingEnabled, false)
}
const manifest = read('android/app/src/main/AndroidManifest.xml')
assert(manifest.includes('android:allowBackup="false"'))
assert(manifest.includes('android:usesCleartextTraffic="false"'))
const paths = read('android/app/src/main/res/xml/file_paths.xml')
assert(!paths.includes('external-path'))
assert(paths.includes('path="eleven-shared-pdf/"'))
assert(paths.includes('<external-files-path name="eleven_camera" path="Pictures/"'))
assert(!paths.includes('path="."') && !paths.includes('path="/"'))
assert(read('ios/App/App/Info.plist').includes('NSCameraUsageDescription'))
assert(read('ios/App/App/PrivacyInfo.xcprivacy').includes('C617.1'))
console.log('Mobile: bundled assets, HTTPS, restricted bridge/files, camera and privacy manifest verified')
