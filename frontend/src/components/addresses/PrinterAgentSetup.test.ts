import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import PrinterAgentSetup from './PrinterAgentSetup.vue'
const api = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/services/api', () => ({ default: api }))
let app: App | undefined, container: HTMLDivElement
const flush = async () => { for (let n = 0; n < 5; n++) await Promise.resolve(); await nextTick() }
afterEach(() => { vi.runOnlyPendingTimers(); vi.useRealTimers(); app?.unmount(); container.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.resetAllMocks() })

describe('Printer agent update', () => {
  it('shows the current queue and recovers an authenticated download failure without printing', async () => {
    vi.useFakeTimers()
    container = document.createElement('div'); document.body.append(container)
    const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
    const refresh = vi.fn()
    app = createApp(PrinterAgentSetup, { device: { id: 'local', name: 'Samsung SL-M2035W', active: true, last_seen_at: null }, onRefresh: refresh }).use(i18n)
    app.mount(container)
    expect(container.textContent).toContain('Samsung SL-M2035W')
    const button = container.querySelector<HTMLButtonElement>('button')!
    api.get.mockRejectedValueOnce(new Error('Network unavailable'))
    button.click(); await flush()
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('Não foi possível baixar')
    expect(button.disabled).toBe(false)
    i18n.global.locale.value = 'es'; await nextTick()
    expect(container.querySelector('summary')?.textContent).toBe('Configurar impresora de la tienda')
    i18n.global.locale.value = 'en'; await nextTick()
    expect(container.querySelector('summary')?.textContent).toBe('Set up store printer')
    const createObjectURL = vi.fn(() => 'blob:local-test')
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL: vi.fn() })
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    api.get.mockResolvedValueOnce({ data: new Blob(['zip fixture']) })
    button.click(); await flush()
    expect(api.get).toHaveBeenLastCalledWith('/api/printing/agent-package', { responseType: 'blob' })
    expect(anchorClick).toHaveBeenCalledOnce()
    expect(container.querySelector('[role="alert"]')).toBeNull()
    container.querySelectorAll<HTMLButtonElement>('button')[1]!.click()
    expect(refresh).toHaveBeenCalledOnce()
  })
})
