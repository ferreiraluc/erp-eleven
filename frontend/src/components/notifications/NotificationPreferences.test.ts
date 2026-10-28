import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import DeliveryStatus from './NotificationPreferences.vue'
const mock = vi.hoisted(() => ({ center: {} as Record<string, unknown>, enable: vi.fn() }))
vi.mock('@/stores/notificationCenter', () => ({ useNotificationCenter: () => mock.center }))
let app: App, root: HTMLElement
beforeEach(() => {
  mock.center = reactive({ pushActive: false, pushError: '', support: 'ready', restoring: false, pushBusy: false, enablePush: mock.enable })
  root = document.createElement('div'); document.body.append(root); app = createApp(DeliveryStatus); app.mount(root)
})
afterEach(() => { app.unmount(); root.remove(); vi.resetAllMocks() })
describe('Company notification delivery status', () => {
  it('offers only the native permission action, with no category, sound or disable preferences', async () => {
    expect(root.querySelector('details,input,select')).toBeNull()
    expect(root.textContent).not.toContain('Preferências')
    root.querySelector('button')!.click(); expect(mock.enable).toHaveBeenCalledOnce()
    mock.center.pushActive = true; await nextTick(); expect(root.textContent).toBe('')
  })
  it('explains denied permission without trying to override the browser', async () => {
    mock.center.support = 'denied'; await nextTick()
    expect(root.textContent).toContain('configurações do navegador')
    expect(root.querySelector('button')).toBeNull(); expect(mock.enable).not.toHaveBeenCalled()
  })
})
