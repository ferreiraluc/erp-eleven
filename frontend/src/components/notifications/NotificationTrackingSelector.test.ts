import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, ref, type App } from 'vue'
import TrackingSelector from './NotificationTrackingSelector.vue'
const mock = vi.hoisted(() => ({ lookup: vi.fn() }))
vi.mock('@/services/notifications', () => ({ notificationsAPI: { contextTracking: mock.lookup } }))
let app: App, root: HTMLElement
const path = ref('/rastreamento'), token = ref<string | null>('owner-session'), loaded = vi.fn()
const tracking = { id: 'fixture', code: 'AA123456789BR', cliente_username: 'Destinatário real', status: 'Em trânsito' }
async function flush() { for (let i = 0; i < 5; i++) await nextTick() }
function type(code: string) { const input = root.querySelector('input')!; input.value = code; input.dispatchEvent(new Event('input', { bubbles: true })) }
beforeEach(async () => {
  vi.useFakeTimers(); path.value = '/rastreamento'; token.value = 'owner-session'; loaded.mockClear()
  mock.lookup.mockResolvedValue(tracking)
  root = document.createElement('div'); document.body.append(root)
  app = createApp({ setup: () => () => h(TrackingSelector, { modelValue: path.value, token: token.value,
    'onUpdate:modelValue': (value: string) => { path.value = value }, onLoaded: loaded }) })
  app.mount(root); await flush()
})
afterEach(() => { app.unmount(); root.remove(); vi.resetAllMocks(); vi.useRealTimers() })
describe('Tracking notification preview selector', () => {
  it('looks up only the entered code and presents its actual recipient and status', async () => {
    type('aa123456789br'); await flush(); await vi.advanceTimersByTimeAsync(300); await flush()
    expect(path.value).toBe('/rastreamento?search=AA123456789BR')
    expect(mock.lookup).toHaveBeenCalledWith('AA123456789BR', 'owner-session', expect.any(AbortSignal))
    expect(root.textContent).toContain('Destinatário real'); expect(root.textContent).toContain('Em trânsito')
    type(''); await flush(); expect(path.value).toBe('/rastreamento'); expect(root.textContent).not.toContain('Destinatário real')
  })
  it('aborts and discards the previous account result when a session changes', async () => {
    let resolve!: (value: typeof tracking) => void
    mock.lookup.mockReturnValueOnce(new Promise(r => { resolve = r }))
    type(tracking.code); await flush(); await vi.advanceTimersByTimeAsync(300)
    const signal = mock.lookup.mock.calls[0][2]
    token.value = null; await flush(); resolve(tracking); await flush()
    expect(signal.aborted).toBe(true); expect(root.textContent).not.toContain('Destinatário real')
    expect(loaded).not.toHaveBeenCalledWith(tracking)
  })
  it('shows an unavailable lookup honestly without reusing a previous recipient', async () => {
    mock.lookup.mockRejectedValueOnce(new Error('missing'))
    type(tracking.code); await flush(); await vi.advanceTimersByTimeAsync(300); await flush()
    expect(root.querySelector('[role=alert]')?.textContent).toContain('Rastreio indisponível')
    expect(root.textContent).not.toContain('Destinatário real')
  })
})
