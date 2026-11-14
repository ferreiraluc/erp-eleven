/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { runInNewContext } from 'node:vm'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const source = readFileSync(resolve('public/download/download.js'), 'utf8')
const html = readFileSync(resolve('public/download/index.html'), 'utf8')
const apk = {
  status: 'ready', version: '1.0.1', sizeBytes: 47_620_427, sha256: 'a'.repeat(64),
  url: 'https://github.com/ferreiraluc/erp-eleven/releases/download/android-v1.0.1/Eleven.apk',
}
const ios = {
  status: 'ready', version: '1.0.1', expiresAt: '2099-11-13T10:00:00Z',
  manifestUrl: 'https://elevenparispy.com/download/ios/manifest.plist',
}
function boot(data: unknown, failure = false) {
  const fetcher = failure ? vi.fn().mockRejectedValue(new Error('offline')) :
    vi.fn().mockResolvedValue({ ok: true, json: async () => data })
  runInNewContext(source, { document, fetch: fetcher, AbortController, setTimeout, clearTimeout, URL, Date })
  return fetcher
}
const element = (id: string) => document.getElementById(id) as HTMLElement
const link = (id: string) => document.getElementById(id) as HTMLAnchorElement

beforeEach(() => { document.body.innerHTML = html.match(/<body>([\s\S]*)<\/body>/)![1]! })

describe('Private app download page', () => {
  it('offers the verified APK and leaves iPhone pending without a fake install link', async () => {
    const fetcher = boot({ schemaVersion: 1, android: apk, ios: { status: 'pending_enrollment' } })
    await vi.waitFor(() => expect(element('android-download').hidden).toBe(false))
    expect(link('android-download').href).toBe(apk.url)
    expect(element('android-sha').textContent).toBe(apk.sha256)
    expect(element('android-pilot').hidden).toBe(true)
    expect(element('ios-install').hidden).toBe(true)
    expect(link('ios-install').hasAttribute('href')).toBe(false)
    expect(fetcher).toHaveBeenCalledWith('/download/releases.json', expect.objectContaining({ cache: 'no-store', credentials: 'omit' }))
  })

  it.each([
    'http://github.com/ferreiraluc/erp-eleven/releases/download/v1/app.apk',
    'https://github.com/other-owner/erp-eleven/releases/download/v1/app.apk',
    'https://github.com.evil.test/ferreiraluc/erp-eleven/releases/download/v1/app.apk',
    'javascript:alert(1)',
    'https://github.com/ferreiraluc/erp-eleven/releases/download/v1/app.apk?redirect=evil',
  ])('does not offer a download with an unexpected URL: %s', async (url) => {
    boot({ schemaVersion: 1, android: { ...apk, url }, ios: { status: 'pending_enrollment' } })
    await vi.waitFor(() => expect(element('android-badge').textContent).toBe('Indisponível'))
    expect(element('android-download').hidden).toBe(true)
    expect(link('android-download').hasAttribute('href')).toBe(false)
  })

  it('generates the iOS installer only for the controlled manifest and a valid profile', async () => {
    boot({ schemaVersion: 1, android: apk, ios })
    await vi.waitFor(() => expect(element('ios-install').hidden).toBe(false))
    const target = new URL(link('ios-install').href)
    expect(target.protocol).toBe('itms-services:')
    expect(target.searchParams.get('url')).toBe(ios.manifestUrl)
    expect(element('ios-meta').textContent).toContain('1.0.1')
  })

  it.each([
    { ...ios, expiresAt: '2020-01-01T00:00:00Z' },
    { ...ios, expiresAt: 'invalid' },
    { ...ios, manifestUrl: 'https://other.test/manifest.plist' },
    { ...ios, manifestUrl: 'https://elevenparispy.com/download/ios/manifest.plist?token=secret' },
  ])('does not start an expired or uncontrolled iPhone installation', async (iosRelease) => {
    boot({ schemaVersion: 1, android: apk, ios: iosRelease })
    await vi.waitFor(() => expect(element('ios-badge').textContent).toBe('Aguardando atualização'))
    expect(element('ios-install').hidden).toBe(true)
    expect(link('ios-install').hasAttribute('href')).toBe(false)
  })

  it('keeps instructions and browser access usable if release metadata cannot load', async () => {
    boot(null, true)
    await vi.waitFor(() => expect(element('release-error').hidden).toBe(false))
    expect(element('android-download').hidden).toBe(true)
    expect(element('ios-install').hidden).toBe(true)
    expect(document.querySelector('a[href="/#/login"]')).not.toBeNull()
    expect(document.getElementById('udid')).not.toBeNull()
  })

  it('renders metadata as text instead of interpreting HTML', async () => {
    boot({ schemaVersion: 1, android: { ...apk, version: '<img src=x onerror=alert(1)>' }, ios: { status: 'pending_enrollment' } })
    await vi.waitFor(() => expect(element('android-meta').hidden).toBe(false))
    expect(element('android-meta').querySelector('img')).toBeNull()
    expect(element('android-meta').textContent).toContain('<img')
  })
})
