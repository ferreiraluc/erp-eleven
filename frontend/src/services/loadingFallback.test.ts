/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { runInNewContext } from 'node:vm'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const source = readFileSync(resolve('public/loading-fallback.js'), 'utf8')
const html = readFileSync(resolve('index.html'), 'utf8')

type Signal = { target?: object; detail?: Error; payload?: Error; error?: Error; reason?: Error; preventDefault?: () => void }
function boot(options: { url?: string; online?: boolean; storageBlocked?: boolean } = {}) {
  const listeners = new Map<string, (event: Signal) => void>()
  const url = new URL(options.url ?? 'https://elevenparispy.com/?source=shortcut#/pdv')
  const replace = vi.fn()
  const replaceState = vi.fn()
  const sessionStorage = options.storageBlocked ? {
    getItem() { throw new Error('Storage denied') },
    setItem() { throw new Error('Storage denied') },
  } : window.sessionStorage
  const win = {
    location: { href: url.href, origin: url.origin, replace },
    navigator: { onLine: options.online ?? true },
    history: { state: { position: 3 }, replaceState },
    sessionStorage,
    addEventListener: (name: string, handler: (event: Signal) => void) => listeners.set(name, handler),
  }
  runInNewContext(source, { window: win, document, URL, Date, setTimeout, clearTimeout })
  return {
    replace, replaceState,
    emit: (name: string, event: Signal = {}) => listeners.get(name)?.(event),
    asset: (tagName = 'SCRIPT', href = '/assets/index-old.js') => listeners.get('error')?.({
      target: { tagName, href, rel: 'stylesheet' },
    }),
  }
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-10-14T20:00:00Z'))
  sessionStorage.clear()
  localStorage.clear()
  document.body.innerHTML = '<div id="app">Carregando aplicação...</div>'
})
afterEach(() => { vi.useRealTimers() })

describe('Recovery independent of missing deployed JS/CSS', () => {
  it('registers before the entry module and is not deferred', () => {
    expect(html.indexOf('src="/loading-fallback.js"')).toBeLessThan(html.indexOf('src="/src/main.ts"'))
    expect(html).toContain('<script src="/loading-fallback.js"></script>')
  })

  it.each(['SCRIPT', 'LINK'])('refreshes a missing %s once, preserving the route and session', tag => {
    localStorage.setItem('auth_token', 'isolated-test-session')
    const app = boot()
    app.asset(tag)
    app.asset(tag)
    expect(app.replace).toHaveBeenCalledTimes(1)
    const next = new URL(app.replace.mock.calls[0]![0])
    expect(next.searchParams.get('source')).toBe('shortcut')
    expect(next.hash).toBe('#/pdv')
    expect(next.searchParams.has('_erp_reload')).toBe(true)
    expect(localStorage.getItem('auth_token')).toBe('isolated-test-session')
  })

  it('does not loop when storage is unavailable and the fresh request also fails', () => {
    const first = boot({ storageBlocked: true })
    first.asset()
    const retry = boot({ storageBlocked: true, url: first.replace.mock.calls[0]![0] })
    retry.asset()
    expect(retry.replace).not.toHaveBeenCalled()
    expect(document.querySelector('[role="alert"]')?.textContent).toContain('Recarregar sistema')
  })

  it('bounds reloads across manual navigations in the same session', () => {
    boot().asset()
    const retry = boot()
    retry.asset()
    expect(retry.replace).not.toHaveBeenCalled()
  })

  it('shows an offline message without reloading or clearing the form', () => {
    const app = boot({ online: false })
    app.asset()
    expect(app.replace).not.toHaveBeenCalled()
    expect(document.querySelector('[role="alert"]')?.textContent).toContain('sem conexão')
    expect(document.getElementById('app')?.textContent).toBe('Carregando aplicação...')
  })

  it('protects an open sale from automatic reload on navigation failure', () => {
    const app = boot()
    app.emit('erp:application-ready')
    document.getElementById('app')!.textContent = 'Venda em edição'
    app.emit('erp:route-load-error', { detail: new Error('Importing a module script failed.') })
    expect(app.replace).not.toHaveBeenCalled()
    expect(document.getElementById('app')?.textContent).toBe('Venda em edição')
    expect(document.querySelector('[role="alert"]')?.textContent).toContain('ainda não salvas')
    document.querySelector<HTMLButtonElement>('#erp-load-recovery button')!.click()
    expect(app.replace).toHaveBeenCalledTimes(1)
  })

  it('recognizes a mounted older build that does not emit the ready event', () => {
    const app = boot()
    document.getElementById('app')!.setAttribute('data-v-app', '')
    vi.advanceTimersByTime(20000)
    expect(document.querySelector('[role="alert"]')).toBeNull()
    app.asset('LINK', '/assets/old-route.css')
    expect(app.replace).not.toHaveBeenCalled()
    expect(document.querySelector('[role="alert"]')?.textContent).toContain('ainda não salvas')
  })

  it('handles Vite CSS preload errors and keeps a single recovery panel', () => {
    const app = boot()
    app.emit('erp:application-ready')
    const preventDefault = vi.fn()
    app.emit('vite:preloadError', { payload: new Error('Unable to preload CSS for /assets/a.css'), preventDefault })
    app.asset('LINK', '/assets/a.css')
    expect(preventDefault).toHaveBeenCalledOnce()
    expect(document.querySelectorAll('#erp-load-recovery')).toHaveLength(1)
    expect(app.replace).not.toHaveBeenCalled()
  })

  it('ignores images, external resources, API errors and unrelated runtime exceptions', () => {
    const app = boot()
    app.asset('IMG')
    app.asset('SCRIPT', 'https://other.example/assets/index.js')
    app.asset('SCRIPT', '/api/items')
    app.emit('error', { detail: new Error('Network error') })
    app.emit('erp:route-load-error', { detail: new Error('Permission denied') })
    expect(app.replace).not.toHaveBeenCalled()
    expect(document.querySelector('[role="alert"]')).toBeNull()
  })

  it('provides a usable action when boot fails for a different reason', () => {
    const app = boot()
    app.emit('erp:boot-error', { detail: new Error('Unknown initialization error') })
    expect(app.replace).not.toHaveBeenCalled()
    expect(document.querySelector('button')?.textContent).toBe('Recarregar sistema')
  })

  it('removes the retry query only after healthy boot and keeps router state', () => {
    const app = boot({ url: 'https://elevenparispy.com/?source=shortcut&_erp_reload=123#/pdv' })
    app.emit('erp:application-ready')
    vi.advanceTimersByTime(20000)
    expect(app.replaceState).toHaveBeenCalledWith({ position: 3 }, '', 'https://elevenparispy.com/?source=shortcut#/pdv')
    expect(document.querySelector('[role="alert"]')).toBeNull()
    expect(app.replace).not.toHaveBeenCalled()
  })

  it('offers a manual action for a stalled load, removing it if loading succeeds', () => {
    const app = boot()
    vi.advanceTimersByTime(15000)
    expect(document.querySelector('button')?.textContent).toBe('Recarregar sistema')
    expect(app.replace).not.toHaveBeenCalled()
    app.emit('erp:application-ready')
    expect(document.querySelector('[role="alert"]')).toBeNull()
  })

  it.each(['error', 'unhandledrejection'])('shows startup diagnostics for %s without exposing error contents', signal => {
    const app = boot()
    const error = new Error('Private request details must not be shown')
    app.emit(signal, { error, reason: error })
    expect(document.querySelector('[role="alert"]')?.textContent).toContain('Diagnóstico:')
    expect(document.body.textContent).not.toContain(error.message)
    expect(app.replace).not.toHaveBeenCalled()
  })

  it('distinguishes waiting for JS from waiting for session/route initialization', () => {
    const app = boot()
    app.emit('erp:entry-ready')
    vi.advanceTimersByTime(15000)
    expect(document.querySelector('small')?.textContent).toContain('TEMPO · SESSAO/ROTA')
  })

  it('recovers failures in release-scoped assets', () => {
    const app = boot()
    app.asset('SCRIPT', '/assets/cd7fe7f80a02/vendor-old.js')
    expect(app.replace).toHaveBeenCalledOnce()
  })
})
